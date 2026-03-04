"""MCP server for VanPilot display control.

Implements a JSON-RPC 2.0 server over stdio that speaks the Model
Context Protocol (MCP). Claude Code agents discover this server via
.mcp.json in the repository root.

Supports three methods:
- initialize: MCP handshake
- tools/list: Enumerate available tools
- tools/call: Invoke a tool handler
"""

import json
import sys
from typing import Optional

from mcp.src.tools import TOOL_DEFINITIONS, get_tool_by_name
from mcp.src.handlers import (
    handle_display_bitmap,
    handle_submit_bitmap,
    handle_get_screenshot,
    handle_calibrate_display,
)

SERVER_INFO = {
    "name": "vanpilot-display",
    "version": "0.1.0",
}

PROTOCOL_VERSION = "2024-11-05"

# Tool name → handler function mapping
_HANDLERS = {
    "display_bitmap": handle_display_bitmap,
    "submit_bitmap": handle_submit_bitmap,
    "get_screenshot": handle_get_screenshot,
    "calibrate_display": handle_calibrate_display,
}


def handle_request(request: dict) -> Optional[dict]:
    """Process a single JSON-RPC 2.0 request and return the response.

    Returns None for notifications (requests without an id).
    """
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    # Notifications (no id) are fire-and-forget
    if request_id is None and method is not None:
        return None

    if method is None:
        return _error_response(request_id, -32600, "Invalid request: missing method")

    if method == "initialize":
        return _handle_initialize(request_id, params)
    elif method == "tools/list":
        return _handle_tools_list(request_id)
    elif method == "tools/call":
        return _handle_tools_call(request_id, params)
    else:
        return _error_response(request_id, -32601, f"Method not found: {method}")


def _handle_initialize(request_id, params: dict) -> dict:
    """Handle the MCP initialize handshake."""
    return _success_response(request_id, {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
        },
        "serverInfo": SERVER_INFO,
    })


def _handle_tools_list(request_id) -> dict:
    """Handle tools/list: return all tool definitions."""
    return _success_response(request_id, {
        "tools": TOOL_DEFINITIONS,
    })


def _handle_tools_call(request_id, params: dict) -> dict:
    """Handle tools/call: dispatch to the appropriate handler."""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return _error_response(request_id, -32601, f"Unknown tool: {tool_name}")

    result = handler(**arguments)
    return _success_response(request_id, {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result),
            }
        ],
    })


def _success_response(request_id, result: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _error_response(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def main():
    """Main entry point: read JSON-RPC requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = _error_response(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
