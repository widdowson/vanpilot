"""Tests for LogTailer wiring in supervisor server startup."""

import os
import unittest
from unittest import mock

from supervisor.src.server import create_server
from supervisor.src.log_tailer import LogTailer


class ServerLogTailerTest(unittest.TestCase):
    """Tests that create_server wires up a LogTailer."""

    def test_create_server_returns_log_tailer(self):
        """create_server should return a LogTailer as the 4th element."""
        server, port, bridge, tailer = create_server(port=0)
        try:
            self.assertIsInstance(tailer, LogTailer)
        finally:
            server.stop(grace=0)

    def test_log_tailer_uses_default_log_dir(self):
        """LogTailer should default to /tmp/vanpilot/logs."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_LOG_DIR", None)
            server, port, bridge, tailer = create_server(port=0)
            try:
                self.assertEqual(tailer._log_dir, "/tmp/vanpilot/logs")
            finally:
                server.stop(grace=0)

    def test_log_tailer_uses_env_var(self):
        """AGENT_LOG_DIR env var overrides the default log directory."""
        with mock.patch.dict(os.environ, {"AGENT_LOG_DIR": "/custom/logs"}):
            server, port, bridge, tailer = create_server(port=0)
            try:
                self.assertEqual(tailer._log_dir, "/custom/logs")
            finally:
                server.stop(grace=0)

    def test_log_tailer_shares_event_store(self):
        """LogTailer should use the same EventStore as the gRPC service."""
        server, port, bridge, tailer = create_server(port=0)
        try:
            # The bridge and tailer should reference the same EventStore
            self.assertIs(tailer._event_store, bridge._event_store)
        finally:
            server.stop(grace=0)


if __name__ == "__main__":
    unittest.main()
