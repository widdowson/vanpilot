"""Golden image comparison with pixel-by-pixel diffing.

Compares a candidate screenshot against a committed golden image.
On mismatch, generates a diff image highlighting changed pixels.
Uses only the standard library (struct + zlib) for PNG I/O.
"""

import os
import struct
import zlib
from typing import Optional

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_pixels(png_data: bytes) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Decode a PNG image into width, height, and flat list of RGB tuples.

    Only supports 8-bit RGB (color type 2) PNGs with a single IDAT chunk
    and filter type 0 (None) — which is what make_png() produces.

    Args:
        png_data: Raw PNG file bytes.

    Returns:
        (width, height, pixels) where pixels is a list of (R, G, B) tuples.

    Raises:
        ValueError: If the PNG format is unsupported.
    """
    if png_data[:8] != PNG_SIGNATURE:
        raise ValueError("Not a valid PNG file")

    pos = 8
    width = height = 0
    idat_chunks = []

    while pos < len(png_data):
        length = struct.unpack(">I", png_data[pos : pos + 4])[0]
        chunk_type = png_data[pos + 4 : pos + 8]
        chunk_data = png_data[pos + 8 : pos + 8 + length]
        pos += 12 + length  # length + type + data + crc

        if chunk_type == b"IHDR":
            w, h, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
            if bit_depth != 8 or color_type != 2:
                raise ValueError(
                    f"Unsupported PNG format: bit_depth={bit_depth}, "
                    f"color_type={color_type} (only 8-bit RGB supported)"
                )
            width, height = w, h
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if not idat_chunks:
        raise ValueError("No IDAT chunks found")

    raw = zlib.decompress(b"".join(idat_chunks))
    pixels = []
    row_bytes = 1 + width * 3  # filter byte + RGB per pixel
    for y in range(height):
        row_start = y * row_bytes
        filter_byte = raw[row_start]
        if filter_byte != 0:
            raise ValueError(f"Unsupported filter type {filter_byte} at row {y}")
        for x in range(width):
            offset = row_start + 1 + x * 3
            r, g, b = raw[offset], raw[offset + 1], raw[offset + 2]
            pixels.append((r, g, b))

    return width, height, pixels


def compare_golden(
    actual_png: bytes,
    golden_png: bytes,
    tolerance: int = 0,
) -> tuple[bool, int, Optional[bytes]]:
    """Compare actual screenshot against golden image.

    Args:
        actual_png: PNG bytes of the captured screenshot.
        golden_png: PNG bytes of the committed golden image.
        tolerance: Per-channel tolerance (0 = exact match).

    Returns:
        (match, diff_count, diff_png) where:
        - match: True if images match within tolerance.
        - diff_count: Number of pixels that differ.
        - diff_png: PNG bytes of the diff image (None if match).
            Changed pixels shown in red, unchanged in dim gray.
    """
    a_w, a_h, a_pixels = read_png_pixels(actual_png)
    g_w, g_h, g_pixels = read_png_pixels(golden_png)

    if a_w != g_w or a_h != g_h:
        # Size mismatch — generate a minimal diff indicator
        diff_png = _make_size_mismatch_png(a_w, a_h, g_w, g_h)
        return False, a_w * a_h, diff_png

    diff_count = 0
    diff_pixels = []

    for i in range(len(a_pixels)):
        ar, ag, ab = a_pixels[i]
        gr, gg, gb = g_pixels[i]
        if (
            abs(ar - gr) > tolerance
            or abs(ag - gg) > tolerance
            or abs(ab - gb) > tolerance
        ):
            diff_count += 1
            diff_pixels.append((255, 0, 0))  # Red for changed
        else:
            # Dim version of actual for context
            diff_pixels.append((ar // 3, ag // 3, ab // 3))

    if diff_count == 0:
        return True, 0, None

    diff_png = _make_png_from_pixels(a_w, a_h, diff_pixels)
    return False, diff_count, diff_png


def _make_png_from_pixels(
    width: int, height: int, pixels: list[tuple[int, int, int]]
) -> bytes:
    """Create a PNG from a flat list of RGB pixel tuples."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    rows = []
    for y in range(height):
        row = b"\x00"  # filter byte
        for x in range(width):
            r, g, b = pixels[y * width + x]
            row += bytes([r, g, b])
        rows.append(row)

    idat = _chunk(b"IDAT", zlib.compress(b"".join(rows)))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def _make_size_mismatch_png(
    actual_w: int, actual_h: int, golden_w: int, golden_h: int
) -> bytes:
    """Create a small PNG indicating a size mismatch."""
    # 100x50 red image as a clear indicator
    from mcp.src.png_util import make_png

    return make_png(100, 50, (255, 0, 0))


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length + type + data + CRC32."""
    raw = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + raw
        + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    )
