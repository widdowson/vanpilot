"""Integration tests for InputInjector using real tmux and a TCP harness.

These tests verify the full injection pipeline:
  1. InputInjector calls ``tmux send-keys``
  2. Keys arrive at a Python TCP client running inside the tmux pane
  3. The client forwards them over TCP to a test harness socket
  4. The test harness verifies the received text and optionally simulates
     an agent response by writing to the conversation log file

Requires ``tmux`` to be installed.  Tests are skipped if it is absent.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import textwrap
import threading
import time
import unittest

from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector
from supervisor.src.tmux_launcher import TmuxLauncher


_HAS_TMUX = shutil.which("tmux") is not None


@unittest.skipUnless(_HAS_TMUX, "tmux is not installed")
class InputInjectorIntegrationTest(unittest.TestCase):
    """End-to-end tests using real tmux sessions and a TCP test harness."""

    def setUp(self):
        # --- TCP server on an ephemeral port ---
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_sock.listen(1)
        self.port = self.server_sock.getsockname()[1]

        # --- Temp directory for logs and the client script ---
        self.tmpdir = tempfile.mkdtemp(prefix="injector-integ-")

        # --- Write a small TCP client that forwards stdin lines over TCP ---
        client_script_path = os.path.join(self.tmpdir, "tcp_client.py")
        with open(client_script_path, "w") as f:
            f.write(textwrap.dedent(f"""\
                import socket, sys
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", {self.port}))
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    s.sendall(line.encode())
                s.close()
            """))

        # --- Unique tmux session name ---
        self.session_name = (
            f"integ-{os.getpid()}-{int(time.time() * 1000) % 100000}"
        )

        # --- Start a tmux session whose pane runs the TCP client ---
        subprocess.run(
            [
                "tmux", "new-session", "-d", "-s", self.session_name,
                "python3", client_script_path,
            ],
            check=True,
        )

        # --- Wait for the client to connect ---
        self.server_sock.settimeout(5.0)
        self.client_conn, _ = self.server_sock.accept()
        self.client_conn.settimeout(5.0)

        # --- InputInjector wired to a real TmuxLauncher ---
        self.store = EventStore()
        self.injector = InputInjector(
            TmuxLauncher(),
            self.store,
            log_dir=self.tmpdir,
            response_timeout_s=1.0,
            poll_interval_s=0.05,
        )

    def tearDown(self):
        subprocess.run(
            ["tmux", "kill-session", "-t", self.session_name],
            capture_output=True,
        )
        try:
            self.client_conn.close()
        except Exception:
            pass
        try:
            self.server_sock.close()
        except Exception:
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _recv_all(self, timeout=5.0):
        """Read available data from the TCP connection.

        Blocks up to *timeout* seconds for the first byte, then drains any
        remaining bytes with a short follow-up timeout.
        """
        self.client_conn.settimeout(timeout)
        chunks: list[bytes] = []
        try:
            while True:
                data = self.client_conn.recv(4096)
                if not data:
                    break
                chunks.append(data)
                # After the first chunk, use a short timeout to drain.
                self.client_conn.settimeout(0.3)
        except socket.timeout:
            pass
        return b"".join(chunks)

    def _seed_log(self) -> str:
        """Create an initial log file for the session and return its path."""
        log_file = os.path.join(self.tmpdir, f"{self.session_name}.jsonl")
        with open(log_file, "w") as f:
            f.write("initial\n")
        return log_file

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_injected_text_arrives_at_tcp_harness(self):
        """tmux send-keys text travels through the pane to the TCP harness."""
        log_file = self._seed_log()

        # Schedule log growth so inject() does not time out.
        def grow_log():
            time.sleep(0.3)
            with open(log_file, "a") as f:
                f.write("response\n")

        threading.Thread(target=grow_log, daemon=True).start()

        result = self.injector.inject(self.session_name, "hello from test")

        self.assertTrue(result)
        data = self._recv_all()
        self.assertIn(b"hello from test", data)

    def test_log_growth_triggered_by_tcp_harness(self):
        """TCP harness receives text, writes to log -> inject() returns True."""
        log_file = self._seed_log()
        received: list[bytes] = []

        def tcp_reader():
            """Read from TCP; simulate agent response by growing the log."""
            try:
                data = self.client_conn.recv(4096)
                received.append(data)
                # Simulate the agent producing output.
                with open(log_file, "a") as f:
                    f.write("agent produced output\n")
            except socket.timeout:
                pass

        reader = threading.Thread(target=tcp_reader, daemon=True)
        reader.start()

        result = self.injector.inject(self.session_name, "process this")

        reader.join(timeout=3.0)
        self.assertTrue(result, "inject() should return True when log grows")
        self.assertTrue(len(received) > 0, "TCP harness should have received data")
        self.assertIn(b"process this", received[0])

    def test_timeout_emits_failure_when_no_log_growth(self):
        """InputDeliveryFailure emitted when log does not grow within timeout."""
        # No log file exists -> no growth possible -> guaranteed timeout.
        result = self.injector.inject(self.session_name, "doomed text", "lead")

        self.assertFalse(result)

        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failures = [e for e in events if e.HasField("input_delivery_failure")]
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            failures[0].input_delivery_failure.attempted_input, "doomed text",
        )
        self.assertEqual(
            failures[0].input_delivery_failure.target_agent_id, "lead",
        )

        # Verify the text was still delivered to the tmux pane.
        data = self._recv_all()
        self.assertIn(b"doomed text", data)


if __name__ == "__main__":
    unittest.main()
