"""Integration test: injected prompt -> agent JSONL log output -> TextMessage event.

Covers the full pipeline:
  1. InputInjector sends a prompt to a tmux session.
  2. The simulated agent appends a JSONL assistant message to the log file.
  3. LogTailer picks up the new entry and adds a TextMessage event to the EventStore.
  4. The EventStore contains the expected TextMessage.

Requires ``tmux`` to be installed.  Tests are skipped if it is absent.
"""

import json
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
from supervisor.src.log_tailer import LogTailer
from supervisor.src.tmux_launcher import TmuxLauncher


_HAS_TMUX = shutil.which("tmux") is not None


@unittest.skipUnless(_HAS_TMUX, "tmux is not installed")
class LogTailerIntegrationTest(unittest.TestCase):
    """End-to-end test: prompt injection -> JSONL agent response -> TextMessage in store."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="log-tailer-integ-")

        # TCP server so we can signal when the simulated agent has received input.
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_sock.listen(1)
        self.port = self.server_sock.getsockname()[1]

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

        self.session_name = f"lt-integ-{os.getpid()}-{int(time.time() * 1000) % 100000}"
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session_name,
             "python3", client_script_path],
            check=True,
        )

        self.server_sock.settimeout(5.0)
        self.client_conn, _ = self.server_sock.accept()
        self.client_conn.settimeout(5.0)

        self.event_store = EventStore()
        self.log_tailer = LogTailer(
            event_store=self.event_store,
            log_dir=self.tmpdir,
            poll_interval_s=0.05,
        )
        self.injector = InputInjector(
            TmuxLauncher(),
            self.event_store,
            log_dir=self.tmpdir,
            response_timeout_s=3.0,
            poll_interval_s=0.05,
        )

    def tearDown(self):
        self.log_tailer.stop()
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

    def _jsonl_assistant_message(self, text: str) -> str:
        return json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }) + "\n"

    def test_inject_prompt_produces_text_message_event(self):
        """Injected prompt -> agent JSONL reply -> TextMessage event in EventStore."""
        log_file = os.path.join(self.tmpdir, f"{self.session_name}.jsonl")

        # Start the LogTailer background thread.
        self.log_tailer.start()

        agent_reply = "I have received your instructions and will proceed."

        def simulate_agent():
            """Wait for input via TCP then write a JSONL assistant response."""
            try:
                self.client_conn.recv(4096)
            except socket.timeout:
                pass
            with open(log_file, "a") as f:
                f.write(self._jsonl_assistant_message(agent_reply))

        agent_thread = threading.Thread(target=simulate_agent, daemon=True)
        agent_thread.start()

        result = self.injector.inject(self.session_name, "start the build", self.session_name)
        agent_thread.join(timeout=3.0)

        self.assertTrue(result, "inject() should return True after log grows")

        # Give LogTailer time to pick up the new entry.
        deadline = time.monotonic() + 2.0
        text_events = []
        while time.monotonic() < deadline:
            all_events = self.event_store.get_events(since_timestamp_ms=0, max_count=200)
            text_events = [
                e for e in all_events
                if e.HasField("text_message")
                and e.text_message.agent_id == self.session_name
                and agent_reply in e.text_message.content
            ]
            if text_events:
                break
            time.sleep(0.05)

        self.assertTrue(
            len(text_events) >= 1,
            "Expected at least one TextMessage event with the agent reply",
        )
        self.assertEqual(text_events[0].text_message.content, agent_reply)


if __name__ == "__main__":
    unittest.main()
