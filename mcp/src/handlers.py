"""Handler implementations for MCP tools.

These provide a local bitmap cache and display state. In production,
the display_bitmap handler will forward commands to the supervisor
via gRPC when the end-to-end wiring is complete (Phase 7).
"""

import base64

from mcp.src.png_util import png_cache_key, make_teal_display

# Module-level bitmap cache: cache_key -> raw PNG bytes
_cache: dict[str, bytes] = {}

# The cache key of the currently displayed bitmap (None = default teal)
_current_display_key: str | None = None


def handle_display_bitmap(cache_key: str, blocking: bool = False) -> dict:
    """Handle the display_bitmap tool call.

    Looks up cache_key in the bitmap cache. If found, sets it as the
    current display. If not found, returns an error.
    """
    global _current_display_key

    if cache_key not in _cache:
        return {"success": False, "error": f"Unknown cache key: {cache_key}"}

    _current_display_key = cache_key
    result = {
        "success": True,
        "cache_key": cache_key,
        "blocking": blocking,
    }
    if blocking:
        result["confirmed_cache_key"] = cache_key
    return result


def handle_submit_bitmap(image_data: str) -> dict:
    """Handle the submit_bitmap tool call.

    Decodes the base64 image data, computes a cache key, stores the
    raw bytes in the cache, and returns the cache key plus a courtesy
    screenshot (the submitted image itself, base64-encoded).
    """
    raw_bytes = base64.b64decode(image_data)
    cache_key = png_cache_key(raw_bytes)
    _cache[cache_key] = raw_bytes

    return {
        "cache_key": cache_key,
        "courtesy_screenshot": base64.b64encode(raw_bytes).decode(),
    }


def handle_get_screenshot() -> dict:
    """Handle the get_screenshot tool call.

    If a bitmap has been displayed, returns that bitmap. Otherwise
    returns the default teal display surface.
    """
    if _current_display_key is not None and _current_display_key in _cache:
        png_bytes = _cache[_current_display_key]
    else:
        png_bytes = make_teal_display()

    return {
        "screenshot": base64.b64encode(png_bytes).decode(),
    }
