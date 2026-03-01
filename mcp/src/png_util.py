"""Pure-Python PNG generation utilities.

Generates valid PNG images using only the standard library (struct + zlib),
avoiding a dependency on Pillow. Used for golden image generation and
default display surfaces.
"""

import struct
import zlib
import hashlib

DISPLAY_WIDTH = 1024
DISPLAY_HEIGHT = 600
TEAL_RGB = (0x1A, 0x8A, 0x7D)


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Generate a solid-color PNG image.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        rgb: (R, G, B) tuple, each 0-255.

    Returns:
        Complete PNG file as bytes.
    """
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit_depth=8, color_type=2 (RGB)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: raw image data with filter byte 0 (None) per row
    r, g, b = rgb
    row = b"\x00" + bytes([r, g, b]) * width  # filter byte + pixel data
    raw_data = row * height
    idat = _chunk(b"IDAT", zlib.compress(raw_data))

    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def make_teal_display() -> bytes:
    """Generate the canonical 1024x600 teal display surface.

    This is the Phase 3 reference image: a solid teal (#1A8A7D) fill
    at the Android Auto display resolution.
    """
    return make_png(DISPLAY_WIDTH, DISPLAY_HEIGHT, TEAL_RGB)


def png_cache_key(png_data: bytes) -> str:
    """Compute a cache key from PNG data.

    Returns a hex string like '0xABCD1234' (0x prefix + 8 uppercase hex chars).
    """
    digest = hashlib.sha256(png_data).hexdigest()[:8]
    return f"0x{digest.upper()}"


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length + type + data + CRC32."""
    raw = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + raw
        + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    )
