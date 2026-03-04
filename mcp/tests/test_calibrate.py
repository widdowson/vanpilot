"""Tests for coordinate calibration module.

TDD: These tests are written BEFORE the implementation in mcp/src/calibrate.py.
"""

import io
import unittest


class PatternGeneratorTest(unittest.TestCase):
    """Tests for generate_calibration_pattern()."""

    def setUp(self):
        from PIL import Image
        from mcp.src.calibrate import generate_calibration_pattern

        self.Image = Image
        self.generate = generate_calibration_pattern

    def test_returns_valid_png(self):
        data = self.generate(1024, 600)
        # PNG signature check
        self.assertTrue(data[:8] == b"\x89PNG\r\n\x1a\n")
        # Should be loadable by Pillow
        img = self.Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "PNG")

    def test_correct_dimensions(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data))
        self.assertEqual(img.size, (1024, 600))

    def test_magenta_background(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        # Center pixel should be magenta
        cx, cy = 512, 300
        self.assertEqual(img.getpixel((cx, cy)), (255, 0, 255))

    def test_top_left_marker_red(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        # Inside the 50x50 top-left marker
        self.assertEqual(img.getpixel((10, 10)), (255, 0, 0))

    def test_top_right_marker_green(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(img.getpixel((1024 - 10, 10)), (0, 255, 0))

    def test_bottom_left_marker_blue(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(img.getpixel((10, 600 - 10)), (0, 0, 255))

    def test_bottom_right_marker_yellow(self):
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(img.getpixel((1024 - 10, 600 - 10)), (255, 255, 0))

    def test_marker_boundaries(self):
        """Pixels just outside markers should be magenta."""
        data = self.generate(1024, 600)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        magenta = (255, 0, 255)
        # Just outside top-left marker
        self.assertEqual(img.getpixel((51, 25)), magenta)
        self.assertEqual(img.getpixel((25, 51)), magenta)

    def test_different_dimensions(self):
        data = self.generate(800, 480)
        img = self.Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(img.size, (800, 480))
        # Markers still at corners
        self.assertEqual(img.getpixel((10, 10)), (255, 0, 0))
        self.assertEqual(img.getpixel((800 - 10, 10)), (0, 255, 0))
        self.assertEqual(img.getpixel((10, 480 - 10)), (0, 0, 255))
        self.assertEqual(img.getpixel((800 - 10, 480 - 10)), (255, 255, 0))


class PatternDetectorTest(unittest.TestCase):
    """Tests for detect_calibration_markers()."""

    def setUp(self):
        from PIL import Image
        from mcp.src.calibrate import (
            generate_calibration_pattern,
            detect_calibration_markers,
        )

        self.Image = Image
        self.generate = generate_calibration_pattern
        self.detect = detect_calibration_markers

    def _composite_pattern_on_screenshot(self, offset_x, offset_y, pat_w, pat_h):
        """Create a 1920x1080 screenshot with calibration pattern composited at offset."""
        screenshot = self.Image.new("RGB", (1920, 1080), (0, 0, 0))
        pattern_data = self.generate(pat_w, pat_h)
        pattern_img = self.Image.open(io.BytesIO(pattern_data))
        screenshot.paste(pattern_img, (offset_x, offset_y))
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return buf.getvalue()

    def test_pattern_at_right_half(self):
        """Pattern occupying right half: x=960, y=0, 960x1080."""
        screenshot_png = self._composite_pattern_on_screenshot(960, 0, 960, 1080)
        markers = self.detect(screenshot_png)
        # Top-left red marker center should be near (960 + 25, 25)
        self.assertAlmostEqual(markers["red_tl"][0], 960 + 25, delta=2)
        self.assertAlmostEqual(markers["red_tl"][1], 25, delta=2)
        # Top-right green marker center near (1920 - 25, 25)
        self.assertAlmostEqual(markers["green_tr"][0], 1920 - 25, delta=2)
        self.assertAlmostEqual(markers["green_tr"][1], 25, delta=2)
        # Bottom-left blue marker center near (960 + 25, 1080 - 25)
        self.assertAlmostEqual(markers["blue_bl"][0], 960 + 25, delta=2)
        self.assertAlmostEqual(markers["blue_bl"][1], 1080 - 25, delta=2)
        # Bottom-right yellow marker center near (1920 - 25, 1080 - 25)
        self.assertAlmostEqual(markers["yellow_br"][0], 1920 - 25, delta=2)
        self.assertAlmostEqual(markers["yellow_br"][1], 1080 - 25, delta=2)

    def test_pattern_full_screen(self):
        """Pattern filling entire 1920x1080."""
        screenshot_png = self._composite_pattern_on_screenshot(0, 0, 1920, 1080)
        markers = self.detect(screenshot_png)
        self.assertAlmostEqual(markers["red_tl"][0], 25, delta=2)
        self.assertAlmostEqual(markers["red_tl"][1], 25, delta=2)
        self.assertAlmostEqual(markers["yellow_br"][0], 1920 - 25, delta=2)
        self.assertAlmostEqual(markers["yellow_br"][1], 1080 - 25, delta=2)

    def test_pattern_at_quarter_screen(self):
        """Pattern at bottom-right quarter: x=960, y=540, 960x540."""
        screenshot_png = self._composite_pattern_on_screenshot(960, 540, 960, 540)
        markers = self.detect(screenshot_png)
        self.assertAlmostEqual(markers["red_tl"][0], 960 + 25, delta=2)
        self.assertAlmostEqual(markers["red_tl"][1], 540 + 25, delta=2)
        self.assertAlmostEqual(markers["yellow_br"][0], 1920 - 25, delta=2)
        self.assertAlmostEqual(markers["yellow_br"][1], 1080 - 25, delta=2)

    def test_returns_all_four_markers(self):
        screenshot_png = self._composite_pattern_on_screenshot(0, 0, 1920, 1080)
        markers = self.detect(screenshot_png)
        self.assertIn("red_tl", markers)
        self.assertIn("green_tr", markers)
        self.assertIn("blue_bl", markers)
        self.assertIn("yellow_br", markers)

    def test_marker_values_are_tuples(self):
        screenshot_png = self._composite_pattern_on_screenshot(0, 0, 1920, 1080)
        markers = self.detect(screenshot_png)
        for key in ("red_tl", "green_tr", "blue_bl", "yellow_br"):
            self.assertIsInstance(markers[key], tuple)
            self.assertEqual(len(markers[key]), 2)


class TransformCalculatorTest(unittest.TestCase):
    """Tests for compute_transform()."""

    def setUp(self):
        from mcp.src.calibrate import compute_transform

        self.compute = compute_transform

    def test_right_half_transform(self):
        """Pattern at right half (960-1920, 0-1080), original 1024x600."""
        markers = {
            "red_tl": (960 + 25, 25),
            "green_tr": (1920 - 25, 25),
            "blue_bl": (960 + 25, 1080 - 25),
            "yellow_br": (1920 - 25, 1080 - 25),
        }
        result = self.compute(markers, (1024, 600))
        # App rect
        self.assertAlmostEqual(result["app_rect"]["left"], 960, delta=5)
        self.assertAlmostEqual(result["app_rect"]["top"], 0, delta=5)
        self.assertAlmostEqual(result["app_rect"]["right"], 1920, delta=5)
        self.assertAlmostEqual(result["app_rect"]["bottom"], 1080, delta=5)
        # Offset
        self.assertAlmostEqual(result["offset_x"], 960, delta=5)
        self.assertAlmostEqual(result["offset_y"], 0, delta=5)
        # Scale: displayed is 960px wide, pattern is 1024px wide
        expected_scale_x = 960.0 / 1024.0
        self.assertAlmostEqual(result["scale_x"], expected_scale_x, places=2)
        expected_scale_y = 1080.0 / 600.0
        self.assertAlmostEqual(result["scale_y"], expected_scale_y, places=2)

    def test_full_screen_transform(self):
        """Pattern fills entire 1920x1080, original 1920x1080."""
        markers = {
            "red_tl": (25, 25),
            "green_tr": (1920 - 25, 25),
            "blue_bl": (25, 1080 - 25),
            "yellow_br": (1920 - 25, 1080 - 25),
        }
        result = self.compute(markers, (1920, 1080))
        self.assertAlmostEqual(result["offset_x"], 0, delta=5)
        self.assertAlmostEqual(result["offset_y"], 0, delta=5)
        self.assertAlmostEqual(result["scale_x"], 1.0, places=2)
        self.assertAlmostEqual(result["scale_y"], 1.0, places=2)

    def test_quarter_screen_transform(self):
        """Pattern at bottom-right quarter (960-1920, 540-1080), original 960x540."""
        markers = {
            "red_tl": (960 + 25, 540 + 25),
            "green_tr": (1920 - 25, 540 + 25),
            "blue_bl": (960 + 25, 1080 - 25),
            "yellow_br": (1920 - 25, 1080 - 25),
        }
        result = self.compute(markers, (960, 540))
        self.assertAlmostEqual(result["offset_x"], 960, delta=5)
        self.assertAlmostEqual(result["offset_y"], 540, delta=5)
        self.assertAlmostEqual(result["scale_x"], 1.0, places=2)
        self.assertAlmostEqual(result["scale_y"], 1.0, places=2)

    def test_result_has_usage_hint(self):
        markers = {
            "red_tl": (25, 25),
            "green_tr": (1895, 25),
            "blue_bl": (25, 1055),
            "yellow_br": (1895, 1055),
        }
        result = self.compute(markers, (1920, 1080))
        self.assertIn("usage", result)
        self.assertIsInstance(result["usage"], str)

    def test_result_has_app_rect(self):
        markers = {
            "red_tl": (25, 25),
            "green_tr": (1895, 25),
            "blue_bl": (25, 1055),
            "yellow_br": (1895, 1055),
        }
        result = self.compute(markers, (1920, 1080))
        rect = result["app_rect"]
        self.assertIn("left", rect)
        self.assertIn("top", rect)
        self.assertIn("right", rect)
        self.assertIn("bottom", rect)


if __name__ == "__main__":
    unittest.main()
