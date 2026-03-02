"""Tests for the MCP server stdio loop.

Verifies that main() correctly:
- Reads JSON-RPC requests from stdin line by line
- Writes JSON-RPC responses to stdout
- Handles malformed JSON with a -32700 parse error
- Skips empty/whitespace lines
- Suppresses output for notifications (no id)
"""

import io
import json
import unittest
from unittest.mock import patch

from mcp.src.server import main


class StdioLoopTest(unittest.TestCase):
    """Tests for main() stdin/stdout processing."""

    def _run_main(self, input_text: str) -> str:
        """Run main() with the given stdin text and return stdout output."""
        stdin = io.StringIO(input_text)
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()
        return stdout.getvalue()

    def test_malformed_json_returns_parse_error(self):
        output = self._run_main("this is not json\n")
        response = json.loads(output.strip())
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertIsNone(response["id"])
        self.assertEqual(response["error"]["code"], -32700)
        self.assertEqual(response["error"]["message"], "Parse error")

    def test_empty_lines_are_skipped(self):
        output = self._run_main("\n\n\n")
        self.assertEqual(output, "")

    def test_whitespace_only_lines_are_skipped(self):
        output = self._run_main("   \n\t\n  \t  \n")
        self.assertEqual(output, "")

    def test_valid_request_produces_json_rpc_response(self):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }
        output = self._run_main(json.dumps(request) + "\n")
        response = json.loads(output.strip())
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("result", response)
        self.assertIn("tools", response["result"])

    def test_notification_produces_no_output(self):
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        output = self._run_main(json.dumps(request) + "\n")
        self.assertEqual(output, "")

    def test_multiple_requests_produce_multiple_responses(self):
        req1 = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        req2 = json.dumps({
            "jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {},
        })
        output = self._run_main(req1 + "\n" + req2 + "\n")
        lines = [line for line in output.strip().split("\n") if line]
        self.assertEqual(len(lines), 2)
        resp1 = json.loads(lines[0])
        resp2 = json.loads(lines[1])
        self.assertEqual(resp1["id"], 1)
        self.assertEqual(resp2["id"], 2)

    def test_mixed_valid_and_invalid_input(self):
        """Malformed JSON doesn't prevent processing subsequent valid requests."""
        lines = [
            "not json",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
        ]
        output = self._run_main("\n".join(lines) + "\n")
        responses = [json.loads(line) for line in output.strip().split("\n") if line]
        self.assertEqual(len(responses), 2)
        # First: parse error
        self.assertEqual(responses[0]["error"]["code"], -32700)
        # Second: valid response
        self.assertEqual(responses[1]["id"], 1)
        self.assertIn("result", responses[1])

    def test_each_response_ends_with_newline(self):
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        output = self._run_main(request + "\n")
        self.assertTrue(output.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
