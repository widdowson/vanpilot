"""Tests for the MCP JSON-RPC server protocol handling.

Verifies that the server correctly handles the MCP protocol:
- initialize handshake
- tools/list to enumerate available tools
- tools/call to invoke tool handlers
- Error handling for invalid requests
"""

import base64
import json
import unittest

from mcp.src import handlers
from mcp.src.server import handle_request, SERVER_INFO


class InitializeTest(unittest.TestCase):
    """Tests for the initialize handshake."""

    def test_initialize_returns_server_info(self):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            },
        }
        response = handle_request(request)
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        result = response["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertIn("serverInfo", result)
        self.assertEqual(result["serverInfo"]["name"], SERVER_INFO["name"])

    def test_initialize_declares_tools_capability(self):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            },
        }
        response = handle_request(request)
        capabilities = response["result"]["capabilities"]
        self.assertIn("tools", capabilities)


class ToolsListTest(unittest.TestCase):
    """Tests for the tools/list method."""

    def test_lists_all_tools(self):
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }
        response = handle_request(request)
        self.assertEqual(response["id"], 2)
        tools = response["result"]["tools"]
        self.assertEqual(len(tools), 3)
        tool_names = {t["name"] for t in tools}
        self.assertEqual(
            tool_names,
            {"display_bitmap", "submit_bitmap", "get_screenshot"},
        )


class ToolsCallTest(unittest.TestCase):
    """Tests for the tools/call method."""

    def setUp(self):
        handlers.reset()

    def test_call_display_bitmap(self):
        # Submit a bitmap first so the cache key exists
        submit_request = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "submit_bitmap",
                "arguments": {
                    "image_data": base64.b64encode(b"test png").decode(),
                },
            },
        }
        submit_response = handle_request(submit_request)
        submit_data = json.loads(submit_response["result"]["content"][0]["text"])
        cache_key = submit_data["cache_key"]

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "display_bitmap",
                "arguments": {"cache_key": cache_key},
            },
        }
        response = handle_request(request)
        self.assertEqual(response["id"], 3)
        content = response["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        result_data = json.loads(content[0]["text"])
        self.assertTrue(result_data["success"])

    def test_call_submit_bitmap(self):
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "submit_bitmap",
                "arguments": {
                    "image_data": base64.b64encode(b"fake png").decode(),
                },
            },
        }
        response = handle_request(request)
        self.assertEqual(response["id"], 4)
        content = response["result"]["content"]
        result_data = json.loads(content[0]["text"])
        self.assertIn("cache_key", result_data)

    def test_call_get_screenshot(self):
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_screenshot",
                "arguments": {},
            },
        }
        response = handle_request(request)
        content = response["result"]["content"]
        result_data = json.loads(content[0]["text"])
        self.assertIn("screenshot", result_data)

    def test_call_unknown_tool_returns_error(self):
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        }
        response = handle_request(request)
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32601)

    def test_call_is_not_error(self):
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "get_screenshot",
                "arguments": {},
            },
        }
        response = handle_request(request)
        self.assertNotIn("isError", response["result"])


class ErrorHandlingTest(unittest.TestCase):
    """Tests for error handling in the JSON-RPC protocol."""

    def test_unknown_method_returns_error(self):
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "unknown/method",
        }
        response = handle_request(request)
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32601)

    def test_missing_method_returns_error(self):
        request = {
            "jsonrpc": "2.0",
            "id": 9,
        }
        response = handle_request(request)
        self.assertIn("error", response)

    def test_response_preserves_request_id(self):
        request = {
            "jsonrpc": "2.0",
            "id": "custom-id-42",
            "method": "tools/list",
        }
        response = handle_request(request)
        self.assertEqual(response["id"], "custom-id-42")

    def test_notification_handling(self):
        """Notifications (no id) for initialized and cancelled should not error."""
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        response = handle_request(request)
        # Notifications should return None (no response)
        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
