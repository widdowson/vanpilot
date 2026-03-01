"""Tests for MCP tool handler implementations.

Verifies that each tool handler returns the expected response
structure, including bitmap caching and display state management.
"""

import base64
import unittest

import mcp.src.handlers as handlers
from mcp.src.handlers import handle_display_bitmap, handle_submit_bitmap, handle_get_screenshot
from mcp.src.png_util import make_teal_display, png_cache_key


class DisplayBitmapHandlerTest(unittest.TestCase):
    """Tests for the display_bitmap tool handler."""

    def setUp(self):
        handlers._cache.clear()
        handlers._current_display_key = None

    def _submit(self, data: bytes = b"fake png data") -> str:
        """Helper: submit a bitmap and return its cache key."""
        image_data = base64.b64encode(data).decode()
        result = handle_submit_bitmap(image_data=image_data)
        return result["cache_key"]

    def test_returns_success(self):
        cache_key = self._submit()
        result = handle_display_bitmap(cache_key=cache_key)
        self.assertTrue(result["success"])

    def test_returns_cache_key(self):
        cache_key = self._submit()
        result = handle_display_bitmap(cache_key=cache_key)
        self.assertEqual(result["cache_key"], cache_key)

    def test_non_blocking_by_default(self):
        cache_key = self._submit()
        result = handle_display_bitmap(cache_key=cache_key)
        self.assertFalse(result["blocking"])

    def test_blocking_mode(self):
        cache_key = self._submit()
        result = handle_display_bitmap(cache_key=cache_key, blocking=True)
        self.assertTrue(result["blocking"])
        self.assertIn("confirmed_cache_key", result)

    def test_blocking_confirms_same_key(self):
        cache_key = self._submit()
        result = handle_display_bitmap(cache_key=cache_key, blocking=True)
        self.assertEqual(result["confirmed_cache_key"], cache_key)

    def test_returns_failure_for_unknown_key(self):
        result = handle_display_bitmap(cache_key="0xDEADBEEF")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("0xDEADBEEF", result["error"])


class SubmitBitmapHandlerTest(unittest.TestCase):
    """Tests for the submit_bitmap tool handler."""

    def setUp(self):
        handlers._cache.clear()
        handlers._current_display_key = None

    def test_returns_cache_key(self):
        image_data = base64.b64encode(b"fake png data").decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("cache_key", result)
        self.assertTrue(len(result["cache_key"]) > 0)

    def test_returns_courtesy_screenshot(self):
        raw = b"fake png data"
        image_data = base64.b64encode(raw).decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("courtesy_screenshot", result)
        decoded = base64.b64decode(result["courtesy_screenshot"])
        self.assertEqual(decoded, raw)

    def test_cache_key_is_hex_format(self):
        image_data = base64.b64encode(b"test image").decode()
        result = handle_submit_bitmap(image_data=image_data)
        cache_key = result["cache_key"]
        # Cache key should start with 0x and be valid hex
        self.assertTrue(cache_key.startswith("0x"))
        int(cache_key, 16)  # Should not raise ValueError

    def test_different_images_get_different_keys(self):
        img1 = base64.b64encode(b"image one").decode()
        img2 = base64.b64encode(b"image two").decode()
        result1 = handle_submit_bitmap(image_data=img1)
        result2 = handle_submit_bitmap(image_data=img2)
        self.assertNotEqual(result1["cache_key"], result2["cache_key"])


class GetScreenshotHandlerTest(unittest.TestCase):
    """Tests for the get_screenshot tool handler."""

    def setUp(self):
        handlers._cache.clear()
        handlers._current_display_key = None

    def test_returns_screenshot(self):
        result = handle_get_screenshot()
        self.assertIn("screenshot", result)

    def test_default_screenshot_is_teal_display(self):
        result = handle_get_screenshot()
        decoded = base64.b64decode(result["screenshot"])
        self.assertEqual(decoded, make_teal_display())

    def test_screenshot_after_display_returns_displayed_bitmap(self):
        """Submit a bitmap, display it, then verify get_screenshot returns it."""
        raw = b"my custom bitmap"
        image_data = base64.b64encode(raw).decode()
        submit_result = handle_submit_bitmap(image_data=image_data)
        cache_key = submit_result["cache_key"]

        handle_display_bitmap(cache_key=cache_key)

        result = handle_get_screenshot()
        decoded = base64.b64decode(result["screenshot"])
        self.assertEqual(decoded, raw)


if __name__ == "__main__":
    unittest.main()
