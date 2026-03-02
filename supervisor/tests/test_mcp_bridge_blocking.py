"""Tests for McpBridge display confirmation wiring (AC-6.3).

McpBridge should wire the AndroidAppClient.get_current_display as the
display confirmer for the MCP handlers, enabling blocking=true to poll
the actual Android app state.

These tests mock EventStore and BitmapStore to avoid proto dependencies
so they can run both via unittest and Bazel.
"""

import unittest
from unittest.mock import MagicMock, patch

import mcp.src.handlers as handlers


class McpBridgeDisplayConfirmerTest(unittest.TestCase):
    """Tests that McpBridge wires up the display confirmer."""

    def setUp(self):
        handlers.reset()

    def tearDown(self):
        handlers.reset()

    def _make_bridge(self, app_client=None):
        """Create a McpBridge with mocked stores to avoid proto imports."""
        # Patch sync_pb2 at import time so McpBridge can be imported
        # without generated proto code
        mock_sync = MagicMock()
        mock_event_store = MagicMock()
        mock_bitmap_store = MagicMock()

        with patch.dict("sys.modules", {"proto.vanpilot.v1.sync_pb2": mock_sync}):
            from supervisor.src.mcp_bridge import McpBridge
            return McpBridge(
                mock_event_store, mock_bitmap_store, app_client=app_client
            )

    def test_bridge_with_app_client_sets_confirmer(self):
        """When constructed with an app_client, McpBridge sets the confirmer."""
        mock_client = MagicMock()
        mock_client.get_current_display.return_value = "0xABCD"
        self._make_bridge(app_client=mock_client)
        self.assertIsNotNone(handlers._display_confirmer)

    def test_bridge_without_app_client_no_confirmer(self):
        """Without an app_client, no confirmer should be set."""
        self._make_bridge()
        self.assertIsNone(handlers._display_confirmer)

    def test_confirmer_delegates_to_app_client(self):
        """The confirmer should call app_client.get_current_display."""
        mock_client = MagicMock()
        mock_client.get_current_display.return_value = "0xBEEF"
        self._make_bridge(app_client=mock_client)
        result = handlers._display_confirmer()
        self.assertEqual(result, "0xBEEF")
        mock_client.get_current_display.assert_called_once()

    def test_confirmer_handles_grpc_error(self):
        """If app_client raises, the confirmer should return empty string."""
        mock_client = MagicMock()
        mock_client.get_current_display.side_effect = Exception("gRPC error")
        self._make_bridge(app_client=mock_client)
        result = handlers._display_confirmer()
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
