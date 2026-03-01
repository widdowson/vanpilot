"""Handler implementations for MCP tools.

These provide a local bitmap cache and display state. The event callback
system allows the supervisor to be notified when bitmaps are submitted
or display commands are issued, enabling gRPC forwarding to the Android app.
"""

import base64
from typing import Callable, Optional

from mcp.src.png_util import png_cache_key, make_teal_display

# Module-level bitmap cache: cache_key -> raw PNG bytes
_cache: dict[str, bytes] = {}

# The cache key of the currently displayed bitmap (None = default teal)
_current_display_key: str | None = None

# Cached default teal display (immutable, generated once)
_default_teal: bytes | None = None

# Optional callback: called with (event_type, cache_key, image_data_or_none)
_event_callback: Optional[Callable] = None


def set_event_callback(callback: Optional[Callable]) -> None:
    """Register a callback for MCP tool events.

    The callback receives (event_type: str, cache_key: str, image_data: bytes | None).
    Event types: "bitmap_submitted", "display_requested".
    """
    global _event_callback
    _event_callback = callback


def reset() -> None:
    """Reset all handler state. Call from test setUp for isolation."""
    global _current_display_key, _default_teal, _event_callback
    _cache.clear()
    _current_display_key = None
    _default_teal = None
    _event_callback = None


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

    if _event_callback is not None:
        _event_callback("display_requested", cache_key, None)

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

    if _event_callback is not None:
        _event_callback("bitmap_submitted", cache_key, raw_bytes)

    return {
        "cache_key": cache_key,
        "courtesy_screenshot": base64.b64encode(raw_bytes).decode(),
    }


def handle_get_screenshot() -> dict:
    """Handle the get_screenshot tool call.

    If a bitmap has been displayed, returns that bitmap. Otherwise
    returns the default teal display surface (1024x600 #1A8A7D).
    """
    global _default_teal
    if _current_display_key is not None and _current_display_key in _cache:
        png_bytes = _cache[_current_display_key]
    else:
        if _default_teal is None:
            _default_teal = make_teal_display()
        png_bytes = _default_teal

    return {
        "screenshot": base64.b64encode(png_bytes).decode(),
    }
