"""Golden image comparison with pixel-by-pixel diffing.

Compares a candidate screenshot against a committed golden image.
On mismatch, generates a diff image highlighting changed pixels.
Uses only the standard library (struct + zlib) for PNG I/O.
"""

import struct
import zlib
from typing import Optional

from mcp.src.png_util import make_png

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth_predictor(a: int, b: int, c: int) -> int:
    """PNG Paeth predictor function per the PNG specification."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    else:
        return c


def _defilter_row(
    filter_type: int,
    raw_row: bytes,
    prev_row: bytes,
    bpp: int,
) -> bytearray:
    """Defilter a single PNG row according to the filter type.

    Args:
        filter_type: PNG filter type (0-4).
        raw_row: The filtered row bytes (without the filter byte).
        prev_row: The defiltered previous row (zeros for the first row).
        bpp: Bytes per pixel (3 for RGB, 4 for RGBA).

    Returns:
        Defiltered row as bytearray.

    Raises:
        ValueError: If the filter type is unknown.
    """
    row = bytearray(len(raw_row))
    if filter_type == 0:  # None
        row[:] = raw_row
    elif filter_type == 1:  # Sub
        for i in range(len(raw_row)):
            left = row[i - bpp] if i >= bpp else 0
            row[i] = (raw_row[i] + left) & 0xFF
    elif filter_type == 2:  # Up
        for i in range(len(raw_row)):
            row[i] = (raw_row[i] + prev_row[i]) & 0xFF
    elif filter_type == 3:  # Average
        for i in range(len(raw_row)):
            left = row[i - bpp] if i >= bpp else 0
            row[i] = (raw_row[i] + (left + prev_row[i]) // 2) & 0xFF
    elif filter_type == 4:  # Paeth
        for i in range(len(raw_row)):
            left = row[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            up_left = prev_row[i - bpp] if i >= bpp else 0
            row[i] = (raw_row[i] + _paeth_predictor(left, up, up_left)) & 0xFF
    else:
        raise ValueError(f"Unknown PNG filter type {filter_type}")
    return row


def read_png_pixels(png_data: bytes) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Decode a PNG image into width, height, and flat list of RGB tuples.

    Supports 8-bit RGB (color type 2) and 8-bit RGBA (color type 6) PNGs.
    RGBA alpha channels are discarded — only RGB values are returned.
    Supports all standard PNG filter types (0-4): None, Sub, Up, Average, Paeth.

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
    color_type = 0
    idat_chunks = []

    while pos < len(png_data):
        length = struct.unpack(">I", png_data[pos : pos + 4])[0]
        chunk_type = png_data[pos + 4 : pos + 8]
        chunk_data = png_data[pos + 8 : pos + 8 + length]
        pos += 12 + length  # length + type + data + crc

        if chunk_type == b"IHDR":
            w, h, bit_depth, ct = struct.unpack(">IIBB", chunk_data[:10])
            if bit_depth != 8 or ct not in (2, 6):
                raise ValueError(
                    f"Unsupported PNG format: bit_depth={bit_depth}, "
                    f"color_type={ct} (only 8-bit RGB and RGBA supported)"
                )
            width, height = w, h
            color_type = ct
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if not idat_chunks:
        raise ValueError("No IDAT chunks found")

    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 3 if color_type == 2 else 4  # bytes per pixel
    stride = width * bpp  # pixel data per row (no filter byte)
    prev_row = bytearray(stride)  # zeros for first row
    pixels = []

    for y in range(height):
        row_start = y * (1 + stride)
        filter_type = raw[row_start]
        raw_row = raw[row_start + 1 : row_start + 1 + stride]
        defiltered = _defilter_row(filter_type, raw_row, prev_row, bpp)
        for x in range(width):
            offset = x * bpp
            r, g, b = defiltered[offset], defiltered[offset + 1], defiltered[offset + 2]
            pixels.append((r, g, b))
        prev_row = defiltered

    return width, height, pixels


def crop_to_app_pane(png_data: bytes, left: int = 76, top: int = 12,
                     right: int = 1908, bottom: int = 1068) -> bytes:
    """Crop a DHU screenshot to just the app content pane.

    The Android Auto DHU screenshot (1920x1080) includes:
    - Top-left corner: clock, signal strength, battery (non-deterministic)
    - Left navigation rail: app icons that vary by installed apps
    - Bottom-left: mic and app drawer buttons

    Cropping to the app pane eliminates all this non-deterministic chrome,
    keeping only the rounded rectangle containing the tab bar and content.

    Default crop coordinates are for the standard 1920x1080 DHU screenshot.
    The app pane is the rounded rectangle right of the nav rail.

    Args:
        png_data: Raw DHU screenshot PNG bytes.
        left: Left edge of the app pane (pixels).
        top: Top edge of the app pane (pixels).
        right: Right edge of the app pane (pixels).
        bottom: Bottom edge of the app pane (pixels).

    Returns:
        Cropped PNG bytes containing only the app content.
    """
    w, h, pixels = read_png_pixels(png_data)
    left = max(0, min(left, w))
    top = max(0, min(top, h))
    right = max(left, min(right, w))
    bottom = max(top, min(bottom, h))
    crop_w = right - left
    crop_h = bottom - top
    cropped = []
    for y in range(top, bottom):
        for x in range(left, right):
            cropped.append(pixels[y * w + x])
    return _make_png_from_pixels(crop_w, crop_h, cropped)


def mask_status_bar(png_data: bytes, rows: int = 100) -> bytes:
    """Replace the top N rows of a PNG with hot pink (FF00FF).

    Used to eliminate phone emulator status bar jitter (clock, battery)
    from golden comparisons. For DHU screenshots, use crop_to_app_pane()
    instead — the AA "status bar" is the left nav rail, not the top.

    Args:
        png_data: Raw PNG file bytes.
        rows: Number of rows from the top to mask.

    Returns:
        New PNG bytes with the top rows painted hot pink.
    """
    w, h, pixels = read_png_pixels(png_data)
    mask_color = (255, 0, 255)
    for i in range(min(rows * w, len(pixels))):
        pixels[i] = mask_color
    return _make_png_from_pixels(w, h, pixels)


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
            diff_pixels.append((255, 0, 0))
        else:
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
    return make_png(100, 50, (255, 0, 0))


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length + type + data + CRC32."""
    raw = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + raw
        + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    )
