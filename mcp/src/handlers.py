"""Stub handler implementations for MCP tools.

These return mock responses and will be replaced with real
implementations that communicate with the supervisor via gRPC
when the end-to-end wiring is complete (Phase 7).
"""

import base64
import hashlib


def handle_display_bitmap(cache_key: str, blocking: bool = False) -> dict:
    """Handle the display_bitmap tool call.

    Stub: Always returns success. In production, this will queue a
    DisplayCommand event to the supervisor, which forwards it to the
    Android app via gRPC.
    """
    result = {
        "success": True,
        "cache_key": cache_key,
        "blocking": blocking,
    }
    if blocking:
        # In production, this would wait for Android app confirmation.
        # Stub: immediately confirm with the same key.
        result["confirmed_cache_key"] = cache_key
    return result


def handle_submit_bitmap(image_data: str) -> dict:
    """Handle the submit_bitmap tool call.

    Stub: Generates a deterministic cache key from the image data hash
    and returns a placeholder courtesy screenshot. In production, this
    will store the bitmap and request the supervisor to render a preview.
    """
    raw_bytes = base64.b64decode(image_data)
    digest = hashlib.sha256(raw_bytes).hexdigest()[:8]
    cache_key = f"0x{digest.upper()}"

    # Stub courtesy screenshot: a 1x1 transparent PNG
    stub_screenshot = _make_stub_png()

    return {
        "cache_key": cache_key,
        "courtesy_screenshot": base64.b64encode(stub_screenshot).decode(),
    }


def handle_get_screenshot() -> dict:
    """Handle the get_screenshot tool call.

    Stub: Returns a placeholder PNG. In production, this will request
    a screenshot from the Android app via the supervisor's gRPC
    reverse call to AndroidAppService.RequestScreenshot.
    """
    stub_screenshot = _make_stub_png()
    return {
        "screenshot": base64.b64encode(stub_screenshot).decode(),
    }


def _make_stub_png() -> bytes:
    """Generate a minimal valid 1x1 pixel PNG (black) for stub responses."""
    # Minimal 1x1 black PNG, hand-crafted per the PNG specification.
    # This avoids a dependency on Pillow for the skeleton.
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB)
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    # IDAT: filter=0, R=0, G=0, B=0
    raw_data = b"\x00\x00\x00\x00"
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend
