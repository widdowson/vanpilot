"""Tests for golden_diff pixel comparison library."""

import os
import struct
import unittest
import zlib

from goldens.golden_diff import compare_golden, read_png_pixels, _defilter_row
from mcp.src.png_util import make_png


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length + type + data + CRC32."""
    raw = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + raw
        + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    )


def _make_filtered_png(
    width: int,
    height: int,
    pixels: list[list[tuple[int, int, int]]],
    filter_type: int,
    color_type: int = 2,
) -> bytes:
    """Build a PNG with a specific filter type applied to all rows.

    Args:
        width: Image width.
        height: Image height.
        pixels: 2D list of (R,G,B) tuples, pixels[y][x].
        filter_type: PNG filter type (0-4) to apply.
        color_type: PNG color type (2=RGB, 6=RGBA).

    Returns:
        Raw PNG bytes.
    """
    bpp = 3 if color_type == 2 else 4

    # Build unfiltered rows as bytearrays
    unfiltered_rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            r, g, b = pixels[y][x]
            row.extend([r, g, b])
            if color_type == 6:
                row.append(255)  # alpha
        unfiltered_rows.append(row)

    # Apply the filter to each row
    filtered_data = bytearray()
    for y in range(height):
        cur = unfiltered_rows[y]
        prev = unfiltered_rows[y - 1] if y > 0 else bytearray(len(cur))
        filtered_data.append(filter_type)

        if filter_type == 0:  # None
            filtered_data.extend(cur)
        elif filter_type == 1:  # Sub
            for i in range(len(cur)):
                left = cur[i - bpp] if i >= bpp else 0
                filtered_data.append((cur[i] - left) & 0xFF)
        elif filter_type == 2:  # Up
            for i in range(len(cur)):
                filtered_data.append((cur[i] - prev[i]) & 0xFF)
        elif filter_type == 3:  # Average
            for i in range(len(cur)):
                left = cur[i - bpp] if i >= bpp else 0
                filtered_data.append((cur[i] - (left + prev[i]) // 2) & 0xFF)
        elif filter_type == 4:  # Paeth
            for i in range(len(cur)):
                left = cur[i - bpp] if i >= bpp else 0
                up = prev[i]
                up_left = prev[i - bpp] if i >= bpp else 0
                # Paeth predictor
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                if pa <= pb and pa <= pc:
                    pr = left
                elif pb <= pc:
                    pr = up
                else:
                    pr = up_left
                filtered_data.append((cur[i] - pr) & 0xFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    idat = _png_chunk(b"IDAT", zlib.compress(bytes(filtered_data)))
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


class ReadPngPixelsTest(unittest.TestCase):
    """Test PNG decoding."""

    def test_decode_solid_color(self):
        png = make_png(2, 2, (255, 0, 128))
        w, h, pixels = read_png_pixels(png)
        self.assertEqual(w, 2)
        self.assertEqual(h, 2)
        self.assertEqual(len(pixels), 4)
        self.assertEqual(pixels[0], (255, 0, 128))

    def test_decode_single_pixel(self):
        png = make_png(1, 1, (10, 20, 30))
        w, h, pixels = read_png_pixels(png)
        self.assertEqual(w, 1)
        self.assertEqual(h, 1)
        self.assertEqual(pixels, [(10, 20, 30)])

    def test_reject_invalid_signature(self):
        with self.assertRaises(ValueError):
            read_png_pixels(b"not a png")

    def test_roundtrip_dimensions(self):
        png = make_png(100, 50, (0, 0, 0))
        w, h, pixels = read_png_pixels(png)
        self.assertEqual(w, 100)
        self.assertEqual(h, 50)
        self.assertEqual(len(pixels), 5000)

    def test_decode_rgba_color_type_6(self):
        """read_png_pixels should decode RGBA PNGs, discarding the alpha channel."""
        width, height = 2, 2
        color = (50, 100, 150, 200)  # RGBA

        # Build a minimal valid RGBA PNG (color type 6) by hand.
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        ihdr = _png_chunk(b"IHDR", ihdr_data)

        rows = []
        for _ in range(height):
            row = b"\x00"  # filter type 0
            for _ in range(width):
                row += bytes(color)
            rows.append(row)
        idat = _png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        iend = _png_chunk(b"IEND", b"")
        rgba_png = sig + ihdr + idat + iend

        w, h, pixels = read_png_pixels(rgba_png)
        self.assertEqual(w, 2)
        self.assertEqual(h, 2)
        self.assertEqual(len(pixels), 4)
        # Alpha should be discarded — only RGB returned
        for pixel in pixels:
            self.assertEqual(pixel, (50, 100, 150))

    def test_compare_golden_with_rgba(self):
        """compare_golden should work when one image is RGBA."""
        width, height = 3, 3
        color_rgb = (50, 100, 150)

        # Make an RGBA PNG with same RGB values
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        ihdr = _png_chunk(b"IHDR", ihdr_data)
        rows = []
        for _ in range(height):
            row = b"\x00"
            for _ in range(width):
                row += bytes(color_rgb) + b"\xff"  # RGBA, full alpha
            rows.append(row)
        idat = _png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        iend = _png_chunk(b"IEND", b"")
        rgba_png = sig + ihdr + idat + iend

        rgb_png = make_png(width, height, color_rgb)

        # RGBA actual vs RGB golden — should match
        match, diff_count, _ = compare_golden(rgba_png, rgb_png)
        self.assertTrue(match)
        self.assertEqual(diff_count, 0)


class PngFilterTest(unittest.TestCase):
    """Test PNG filter type defiltering (Sub, Up, Average, Paeth)."""

    def _gradient_pixels(self, width, height):
        """Generate a gradient image for realistic filter testing."""
        pixels = []
        for y in range(height):
            row = []
            for x in range(width):
                r = (x * 37 + y * 13) % 256
                g = (x * 59 + y * 7) % 256
                b = (x * 23 + y * 41) % 256
                row.append((r, g, b))
            pixels.append(row)
        return pixels

    def test_filter_type_0_none(self):
        """Filter type 0 (None) — identity, no transformation."""
        pixels = self._gradient_pixels(4, 4)
        png = _make_filtered_png(4, 4, pixels, filter_type=0)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 4)
        self.assertEqual(h, 4)
        for y in range(4):
            for x in range(4):
                self.assertEqual(decoded[y * 4 + x], pixels[y][x])

    def test_filter_type_1_sub(self):
        """Filter type 1 (Sub) — each byte uses the left neighbor as predictor."""
        pixels = self._gradient_pixels(8, 4)
        png = _make_filtered_png(8, 4, pixels, filter_type=1)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 8)
        self.assertEqual(h, 4)
        for y in range(4):
            for x in range(8):
                self.assertEqual(decoded[y * 8 + x], pixels[y][x])

    def test_filter_type_2_up(self):
        """Filter type 2 (Up) — each byte uses the above neighbor as predictor."""
        pixels = self._gradient_pixels(4, 8)
        png = _make_filtered_png(4, 8, pixels, filter_type=2)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 4)
        self.assertEqual(h, 8)
        for y in range(8):
            for x in range(4):
                self.assertEqual(decoded[y * 4 + x], pixels[y][x])

    def test_filter_type_3_average(self):
        """Filter type 3 (Average) — uses average of left and above."""
        pixels = self._gradient_pixels(6, 6)
        png = _make_filtered_png(6, 6, pixels, filter_type=3)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 6)
        self.assertEqual(h, 6)
        for y in range(6):
            for x in range(6):
                self.assertEqual(decoded[y * 6 + x], pixels[y][x])

    def test_filter_type_4_paeth(self):
        """Filter type 4 (Paeth) — uses Paeth predictor of left, above, upper-left."""
        pixels = self._gradient_pixels(5, 5)
        png = _make_filtered_png(5, 5, pixels, filter_type=4)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 5)
        self.assertEqual(h, 5)
        for y in range(5):
            for x in range(5):
                self.assertEqual(decoded[y * 5 + x], pixels[y][x])

    def test_filter_sub_with_rgba(self):
        """Filter type 1 (Sub) with RGBA color type — alpha discarded."""
        pixels = self._gradient_pixels(4, 3)
        png = _make_filtered_png(4, 3, pixels, filter_type=1, color_type=6)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 4)
        self.assertEqual(h, 3)
        for y in range(3):
            for x in range(4):
                self.assertEqual(decoded[y * 4 + x], pixels[y][x])

    def test_filter_paeth_with_rgba(self):
        """Filter type 4 (Paeth) with RGBA color type — alpha discarded."""
        pixels = self._gradient_pixels(4, 4)
        png = _make_filtered_png(4, 4, pixels, filter_type=4, color_type=6)
        w, h, decoded = read_png_pixels(png)
        self.assertEqual(w, 4)
        self.assertEqual(h, 4)
        for y in range(4):
            for x in range(4):
                self.assertEqual(decoded[y * 4 + x], pixels[y][x])

    def test_unknown_filter_type_raises(self):
        """Unknown filter type 5 should raise ValueError."""
        with self.assertRaises(ValueError):
            _defilter_row(5, b"\x00\x00\x00", bytearray(3), 3)

    def test_compare_golden_with_filtered_png(self):
        """compare_golden should work with filter type 1 (Sub) PNGs."""
        pixels = self._gradient_pixels(10, 10)
        actual = _make_filtered_png(10, 10, pixels, filter_type=1)
        golden = _make_filtered_png(10, 10, pixels, filter_type=0)
        match, diff_count, _ = compare_golden(actual, golden)
        self.assertTrue(match)
        self.assertEqual(diff_count, 0)


class CompareGoldenTest(unittest.TestCase):
    """Test golden image comparison."""

    def test_identical_images_match(self):
        png = make_png(10, 10, (100, 200, 50))
        match, diff_count, diff_png = compare_golden(png, png)
        self.assertTrue(match)
        self.assertEqual(diff_count, 0)
        self.assertIsNone(diff_png)

    def test_different_images_do_not_match(self):
        actual = make_png(10, 10, (255, 0, 0))
        golden = make_png(10, 10, (0, 255, 0))
        match, diff_count, diff_png = compare_golden(actual, golden)
        self.assertFalse(match)
        self.assertEqual(diff_count, 100)  # All 10x10 pixels differ
        self.assertIsNotNone(diff_png)

    def test_diff_png_is_valid(self):
        actual = make_png(10, 10, (255, 0, 0))
        golden = make_png(10, 10, (0, 255, 0))
        _, _, diff_png = compare_golden(actual, golden)
        self.assertTrue(diff_png.startswith(b"\x89PNG\r\n\x1a\n"))
        # Should be decodable
        w, h, pixels = read_png_pixels(diff_png)
        self.assertEqual(w, 10)
        self.assertEqual(h, 10)

    def test_diff_pixels_are_red(self):
        actual = make_png(2, 2, (255, 0, 0))
        golden = make_png(2, 2, (0, 255, 0))
        _, _, diff_png = compare_golden(actual, golden)
        _, _, pixels = read_png_pixels(diff_png)
        # All pixels should be red (changed)
        for pixel in pixels:
            self.assertEqual(pixel, (255, 0, 0))

    def test_unchanged_pixels_are_dim(self):
        actual = make_png(2, 2, (90, 90, 90))
        golden = make_png(2, 2, (90, 90, 90))
        match, diff_count, diff_png = compare_golden(actual, golden)
        self.assertTrue(match)
        self.assertEqual(diff_count, 0)

    def test_tolerance_allows_small_differences(self):
        actual = make_png(5, 5, (100, 100, 100))
        golden = make_png(5, 5, (102, 98, 101))
        # With tolerance=0, should not match
        match, _, _ = compare_golden(actual, golden, tolerance=0)
        self.assertFalse(match)
        # With tolerance=5, should match
        match, diff_count, _ = compare_golden(actual, golden, tolerance=5)
        self.assertTrue(match)
        self.assertEqual(diff_count, 0)

    def test_size_mismatch_fails(self):
        actual = make_png(10, 10, (0, 0, 0))
        golden = make_png(20, 20, (0, 0, 0))
        match, diff_count, diff_png = compare_golden(actual, golden)
        self.assertFalse(match)
        self.assertGreater(diff_count, 0)
        self.assertIsNotNone(diff_png)

    def test_diff_output_saved_to_undeclared(self):
        """Verify diff image is a valid PNG that can be saved."""
        actual = make_png(4, 4, (255, 0, 0))
        golden = make_png(4, 4, (0, 0, 255))
        _, _, diff_png = compare_golden(actual, golden)
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp")
        path = os.path.join(undeclared, "test_diff.png")
        with open(path, "wb") as f:
            f.write(diff_png)
        # Verify file was written
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)


if __name__ == "__main__":
    unittest.main()
