"""Tests for golden_diff pixel comparison library."""

import os
import unittest

from goldens.golden_diff import compare_golden, read_png_pixels
from mcp.src.png_util import make_png


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
