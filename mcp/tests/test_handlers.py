"""Tests for MCP tool handler stub implementations.

Verifies that each tool handler returns the expected mock response
structure. These are stubs that will be replaced with real
implementations when the supervisor and gRPC wiring are complete.
"""

import base64
import unittest

from mcp.src.handlers import handle_display_bitmap, handle_submit_bitmap, handle_get_screenshot


class DisplayBitmapHandlerTest(unittest.TestCase):
    """Tests for the display_bitmap tool handler."""

    def test_returns_success(self):
        result = handle_display_bitmap(cache_key="0xDEADBEEF")
        self.assertTrue(result["success"])

    def test_returns_cache_key(self):
        result = handle_display_bitmap(cache_key="0xCAFEBABE")
        self.assertEqual(result["cache_key"], "0xCAFEBABE")

    def test_non_blocking_by_default(self):
        result = handle_display_bitmap(cache_key="0xDEADBEEF")
        self.assertFalse(result["blocking"])

    def test_blocking_mode(self):
        result = handle_display_bitmap(cache_key="0xDEADBEEF", blocking=True)
        self.assertTrue(result["blocking"])
        self.assertIn("confirmed_cache_key", result)

    def test_blocking_confirms_same_key(self):
        result = handle_display_bitmap(cache_key="0xABCD1234", blocking=True)
        self.assertEqual(result["confirmed_cache_key"], "0xABCD1234")


class SubmitBitmapHandlerTest(unittest.TestCase):
    """Tests for the submit_bitmap tool handler."""

    def test_returns_cache_key(self):
        image_data = base64.b64encode(b"fake png data").decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("cache_key", result)
        self.assertTrue(len(result["cache_key"]) > 0)

    def test_returns_courtesy_screenshot(self):
        image_data = base64.b64encode(b"fake png data").decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("courtesy_screenshot", result)
        # The courtesy screenshot should be base64-encoded data
        decoded = base64.b64decode(result["courtesy_screenshot"])
        self.assertTrue(len(decoded) > 0)

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

    def test_returns_screenshot(self):
        result = handle_get_screenshot()
        self.assertIn("screenshot", result)

    def test_screenshot_is_base64_encoded(self):
        result = handle_get_screenshot()
        decoded = base64.b64decode(result["screenshot"])
        self.assertTrue(len(decoded) > 0)


if __name__ == "__main__":
    unittest.main()
