"""Tests for pure-Python PNG generation utilities."""

import struct
import unittest

from mcp.src.png_util import (
    make_png,
    make_teal_display,
    png_cache_key,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    TEAL_RGB,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class MakePngTest(unittest.TestCase):
    """Tests for make_png()."""

    def test_starts_with_png_signature(self):
        png = make_png(1, 1, (0, 0, 0))
        self.assertEqual(png[:8], PNG_SIGNATURE)

    def test_ihdr_contains_correct_dimensions(self):
        png = make_png(32, 16, (255, 0, 0))
        # IHDR is the first chunk after the 8-byte signature.
        # Chunk layout: 4-byte length + 4-byte type + data + 4-byte CRC
        # IHDR data starts at offset 16 (8 sig + 4 len + 4 type)
        ihdr_data = png[16:29]  # 13 bytes of IHDR data
        width, height = struct.unpack(">II", ihdr_data[:8])
        self.assertEqual(width, 32)
        self.assertEqual(height, 16)

    def test_deterministic_output(self):
        png1 = make_png(10, 10, (128, 64, 32))
        png2 = make_png(10, 10, (128, 64, 32))
        self.assertEqual(png1, png2)

    def test_different_colors_produce_different_pngs(self):
        red = make_png(4, 4, (255, 0, 0))
        blue = make_png(4, 4, (0, 0, 255))
        self.assertNotEqual(red, blue)

    def test_1x1_black_is_valid_png(self):
        png = make_png(1, 1, (0, 0, 0))
        self.assertTrue(len(png) > 8)
        self.assertEqual(png[:8], PNG_SIGNATURE)


class MakeTealDisplayTest(unittest.TestCase):
    """Tests for make_teal_display()."""

    def test_is_valid_png(self):
        png = make_teal_display()
        self.assertEqual(png[:8], PNG_SIGNATURE)

    def test_has_correct_dimensions(self):
        png = make_teal_display()
        ihdr_data = png[16:29]
        width, height = struct.unpack(">II", ihdr_data[:8])
        self.assertEqual(width, DISPLAY_WIDTH)
        self.assertEqual(height, DISPLAY_HEIGHT)

    def test_reasonable_file_size(self):
        png = make_teal_display()
        # A 1024x600 solid color PNG should compress well: 1KB-50KB
        self.assertGreater(len(png), 1024)
        self.assertLess(len(png), 50 * 1024)

    def test_deterministic(self):
        png1 = make_teal_display()
        png2 = make_teal_display()
        self.assertEqual(png1, png2)


class PngCacheKeyTest(unittest.TestCase):
    """Tests for png_cache_key()."""

    def test_starts_with_0x_prefix(self):
        key = png_cache_key(b"some data")
        self.assertTrue(key.startswith("0x"))

    def test_is_valid_hex(self):
        key = png_cache_key(b"some data")
        int(key, 16)  # Should not raise ValueError

    def test_has_correct_length(self):
        key = png_cache_key(b"data")
        # 0x + 8 hex chars = 10 chars total
        self.assertEqual(len(key), 10)

    def test_deterministic(self):
        key1 = png_cache_key(b"hello")
        key2 = png_cache_key(b"hello")
        self.assertEqual(key1, key2)

    def test_different_data_different_keys(self):
        key1 = png_cache_key(b"alpha")
        key2 = png_cache_key(b"beta")
        self.assertNotEqual(key1, key2)


if __name__ == "__main__":
    unittest.main()
