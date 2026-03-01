"""MCP tool definitions for the VanPilot display control server.

Defines the three MCP tools that Claude Code agents use to control
the Android Auto head unit display:
- display_bitmap: Show a cached bitmap on the display
- submit_bitmap: Submit a new bitmap for caching
- get_screenshot: Capture the current display
"""

from typing import Optional

TOOL_DEFINITIONS = [
    {
        "name": "display_bitmap",
        "description": (
            "Instruct the Android Auto head unit to display a previously "
            "cached bitmap. By default non-blocking (fire-and-forget). "
            "Set blocking=true to wait for the app to confirm display."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cache_key": {
                    "type": "string",
                    "description": "Hex cache key of the bitmap to display (e.g., '0xDEADBEEF').",
                },
                "blocking": {
                    "type": "boolean",
                    "description": (
                        "If true, wait for the Android app to confirm it is "
                        "displaying the bitmap. Default: false."
                    ),
                    "default": False,
                },
            },
            "required": ["cache_key"],
        },
    },
    {
        "name": "submit_bitmap",
        "description": (
            "Submit a rendered bitmap (PNG) for caching. Returns the assigned "
            "hex cache key and a courtesy screenshot showing how it looks on "
            "the display at the correct dimensions. Use this to verify "
            "rendering before calling display_bitmap."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {
                    "type": "string",
                    "description": "Base64-encoded PNG image data.",
                },
            },
            "required": ["image_data"],
        },
    },
    {
        "name": "get_screenshot",
        "description": (
            "Request a screenshot of the current Android Auto display. "
            "Returns a base64-encoded PNG. Use for troubleshooting or "
            "verifying what is currently shown on the head unit."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def get_tool_by_name(name: str) -> Optional[dict]:
    """Look up a tool definition by name. Returns None if not found."""
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == name:
            return tool
    return None
