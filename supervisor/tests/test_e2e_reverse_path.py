"""End-to-end integration test for the reverse path.

Tests the full round-trip: Android gRPC SendUserInput -> supervisor
SyncService -> InputInjector -> tmux send-keys -> simulated agent ->
EventStore -> gRPC GetEvents -> Android receives result.

This complements test_e2e_grpc.py (forward path) by exercising the
user input -> agent -> response/failure round-trip.

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

import grpc
from concurrent import futures

from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import add_sync_service_to_server
from supervisor.src.tmux_launcher import TmuxLauncher
from proto.vanpilot.v1 import sync_pb2


_HAS_TMUX = shutil.which("tmux") is not None


@unittest.skipUnless(_HAS_TMUX, "tmux is not installed")
class ReversePathEndToEndTest(unittest.TestCase):
    """Full reverse-path test: gRPC SendUserInput -> InputInjector -> tmux -> GetEvents."""

    def setUp(self):
        # --- Unique agent ID to avoid session name collisions ---
        self.agent_id = f"e2e-{os.getpid()}-{int(time.time() * 1000) % 100000}"
        self.session_name = f"vanpilot-{self.agent_id}"

        # --- TCP server on an ephemeral port ---
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_sock.listen(1)
        self.tcp_port = self.server_sock.getsockname()[1]

        # --- Temp directory for logs and the client script ---
        self.tmpdir = tempfile.mkdtemp(prefix="e2e-reverse-")

        # --- Write a small TCP client that forwards stdin lines over TCP ---
        client_script_path = os.path.join(self.tmpdir, "tcp_client.py")
        with open(client_script_path, "w") as f:
            f.write(textwrap.dedent(f"""\
                import socket, sys
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", {self.tcp_port}))
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    s.sendall(line.encode())
                s.close()
            """))

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

        # --- Build the full pipeline ---
        self.event_store = EventStore()
        self.injector = InputInjector(
            TmuxLauncher(),
            self.event_store,
            log_dir=self.tmpdir,
            response_timeout_s=1.0,
            poll_interval_s=0.05,
        )

        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        add_sync_service_to_server(
            self.grpc_server,
            self.event_store,
            BitmapStore(),
            input_injector=self.injector,
        )
        self.grpc_port = self.grpc_server.add_insecure_port("[::]:0")
        self.grpc_server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.grpc_port}")

    def tearDown(self):
        self.channel.close()
        self.grpc_server.stop(grace=0)
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

    def _send_user_input(self, text, agent_id=None):
        """Call SendUserInput over gRPC."""
        request = sync_pb2.SendUserInputRequest(text=text)
        if agent_id is not None:
            request.target_agent_id = agent_id
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/SendUserInput",
            request_serializer=sync_pb2.SendUserInputRequest.SerializeToString,
            response_deserializer=sync_pb2.SendUserInputResponse.FromString,
        )(request)

    def _get_events(self, since_ms=0, max_count=100):
        """Call GetEvents over gRPC."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=since_ms,
            max_count=max_count,
        )
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )(request)

    def _recv_all(self, timeout=5.0):
        """Read available data from the TCP connection."""
        self.client_conn.settimeout(timeout)
        chunks: list[bytes] = []
        try:
            while True:
                data = self.client_conn.recv(4096)
                if not data:
                    break
                chunks.append(data)
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

    def test_full_round_trip_success(self):
        """SendUserInput -> tmux -> TCP harness -> log growth -> no failure in GetEvents."""
        log_file = self._seed_log()
        received: list[bytes] = []

        def tcp_reader_and_responder():
            """Read from TCP; simulate agent response by growing the log."""
            try:
                data = self.client_conn.recv(4096)
                received.append(data)
                # Simulate the agent producing output.
                with open(log_file, "a") as f:
                    f.write("agent response output\n")
            except socket.timeout:
                pass

        reader = threading.Thread(target=tcp_reader_and_responder, daemon=True)
        reader.start()

        # Send input via gRPC (as Android app would)
        response = self._send_user_input("build the project", self.agent_id)
        self.assertTrue(response.accepted)

        # Wait for the injection thread to complete
        reader.join(timeout=3.0)
        time.sleep(0.5)

        # Verify text arrived at the simulated agent
        self.assertTrue(len(received) > 0, "TCP harness should have received data")
        self.assertIn(b"build the project", received[0])

        # Poll GetEvents — should have no InputDeliveryFailure
        events_response = self._get_events()
        failures = [
            e for e in events_response.events
            if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failures), 0, "No failure event expected on success")

    def test_full_round_trip_timeout_produces_failure_event(self):
        """SendUserInput -> tmux -> no response -> InputDeliveryFailure in GetEvents."""
        # No log file seeded -> no growth possible -> guaranteed timeout

        # Send input via gRPC
        response = self._send_user_input("doomed input", self.agent_id)
        self.assertTrue(response.accepted)

        # Verify the text still arrives at the simulated agent
        data = self._recv_all()
        self.assertIn(b"doomed input", data)

        # Wait for the injection thread to time out (1.0s timeout + margin)
        time.sleep(1.5)

        # Poll GetEvents — should contain an InputDeliveryFailure
        events_response = self._get_events()
        failures = [
            e for e in events_response.events
            if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            failures[0].input_delivery_failure.attempted_input, "doomed input",
        )
        self.assertEqual(
            failures[0].input_delivery_failure.target_agent_id, self.agent_id,
        )

    def test_send_user_input_returns_accepted_immediately(self):
        """SendUserInput should return accepted=True without blocking on delivery."""
        self._seed_log()

        start = time.monotonic()
        response = self._send_user_input("quick check", self.agent_id)
        elapsed = time.monotonic() - start

        self.assertTrue(response.accepted)
        # inject_async is fire-and-forget, so the RPC should return quickly
        self.assertLess(elapsed, 0.5, "SendUserInput should not block on injection")


if __name__ == "__main__":
    unittest.main()
