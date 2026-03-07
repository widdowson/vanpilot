"""Tests for display_bitmap(blocking=true) through the MCP JSON-RPC server (AC-6.3).

Verifies that the full MCP protocol path correctly handles blocking mode:
- tools/call with blocking=true polls the confirmer and returns confirmed_cache_key
- tools/call with blocking=true and no confirmer returns an error
- tools/call with blocking=true timeout returns an error
"""

import base64
import json
import unittest

from mcp.src import handlers
from mcp.src.server import handle_request


class ServerBlockingDisplayTest(unittest.TestCase):
    """Tests that blocking=true works end-to-end through the JSON-RPC server."""

    def setUp(self):
        handlers.reset()

    def _submit_via_server(self, tag: str) -> str:
        """Submit a bitmap through the server and return the cache key."""
        request = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "submit_bitmap",
                "arguments": {
                    "image_data": base64.b64encode(
                        b"png-data-" + tag.encode()
                    ).decode(),
                },
            },
        }
        response = handle_request(request)
        result_data = json.loads(response["result"]["content"][0]["text"])
        return result_data["cache_key"]

    def _display_via_server(self, cache_key: str, blocking: bool) -> dict:
        """Call display_bitmap through the server and return parsed result."""
        request = {
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/call",
            "params": {
                "name": "display_bitmap",
                "arguments": {"cache_key": cache_key, "blocking": blocking},
            },
        }
        response = handle_request(request)
        return json.loads(response["result"]["content"][0]["text"])

    def test_blocking_true_returns_confirmed_key(self):
        key = self._submit_via_server("srv-b1")
        handlers.set_display_confirmer(lambda: key)
        result = self._display_via_server(key, blocking=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["blocking"])
        self.assertEqual(result["confirmed_cache_key"], key)

    def test_blocking_false_returns_no_confirmed_key(self):
        key = self._submit_via_server("srv-b2")
        result = self._display_via_server(key, blocking=False)
        self.assertTrue(result["success"])
        self.assertFalse(result["blocking"])
        self.assertNotIn("confirmed_cache_key", result)

    def test_blocking_without_confirmer_returns_error(self):
        key = self._submit_via_server("srv-b3")
        # No confirmer set
        result = self._display_via_server(key, blocking=True)
        self.assertFalse(result["success"])
        self.assertIn("confirmer", result["error"].lower())

    def test_blocking_timeout_returns_error(self):
        key = self._submit_via_server("srv-b4")
        handlers.set_display_confirmer(lambda: "")  # Never confirms
        request = {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "tools/call",
            "params": {
                "name": "display_bitmap",
                "arguments": {"cache_key": key, "blocking": True},
            },
        }
        # Use a short timeout by calling handler directly with timeout override
        # since timeout_seconds is intentionally not exposed in the MCP schema
        result = handlers.handle_display_bitmap(
            cache_key=key, blocking=True, timeout_seconds=0.3
        )
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    def test_blocking_polls_until_confirmed(self):
        key = self._submit_via_server("srv-b5")
        call_count = 0

        def confirmer():
            nonlocal call_count
            call_count += 1
            return key if call_count >= 2 else ""

        handlers.set_display_confirmer(confirmer)
        result = self._display_via_server(key, blocking=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["confirmed_cache_key"], key)
        self.assertGreaterEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
