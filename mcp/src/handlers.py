"""Handler implementations for MCP tools.

These provide a local bitmap cache and display state. The event callback
system allows the supervisor to be notified when bitmaps are submitted
or display commands are issued, enabling gRPC forwarding to the Android app.
"""

import base64
import hashlib
import struct
import zlib
from typing import Callable, Optional

_cache: dict[str, bytes] = {}
_current_display_key: str | None = None
_event_callback: Optional[Callable] = None


def set_event_callback(callback: Optional[Callable]) -> None:
    """Register a callback for MCP tool events."""
    global _event_callback
    _event_callback = callback


def reset() -> None:
    """Reset all handler state. Call from test setUp for isolation."""
    global _current_display_key, _event_callback
    _cache.clear()
    _current_display_key = None
    _event_callback = None


def handle_display_bitmap(cache_key: str, blocking: bool = False) -> dict:
    """Handle the display_bitmap tool call."""
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
    """Handle the submit_bitmap tool call."""
    raw_bytes = base64.b64decode(image_data)
    digest = hashlib.sha256(raw_bytes).hexdigest()[:8]
    cache_key = f"0x{digest.upper()}"
    _cache[cache_key] = raw_bytes

    if _event_callback is not None:
        _event_callback("bitmap_submitted", cache_key, raw_bytes)

    return {
        "cache_key": cache_key,
        "courtesy_screenshot": base64.b64encode(raw_bytes).decode(),
    }


def handle_get_screenshot() -> dict:
    """Handle the get_screenshot tool call."""
    if _current_display_key is not None and _current_display_key in _cache:
        png_bytes = _cache[_current_display_key]
    else:
        png_bytes = _make_stub_png()

    return {
        "screenshot": base64.b64encode(png_bytes).decode(),
    }


def _make_stub_png() -> bytes:
    """Generate a minimal valid 1x1 pixel PNG (black) for stub responses."""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_data = b"\x00\x00\x00\x00"
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend
