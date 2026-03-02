"""Tests for MCP tool handler implementations."""

import base64
import unittest

import mcp.src.handlers as handlers
from mcp.src.handlers import (
    handle_display_bitmap,
    handle_submit_bitmap,
    handle_get_screenshot,
    set_event_callback,
    set_display_confirmer,
)


class DisplayBitmapHandlerTest(unittest.TestCase):

    def setUp(self):
        handlers.reset()

    def _submit(self, tag):
        img = base64.b64encode(b"png-data-" + tag.encode()).decode()
        return handle_submit_bitmap(image_data=img)["cache_key"]

    def test_returns_success(self):
        key = self._submit("s1")
        result = handle_display_bitmap(cache_key=key)
        self.assertTrue(result["success"])

    def test_returns_cache_key(self):
        key = self._submit("s2")
        result = handle_display_bitmap(cache_key=key)
        self.assertEqual(result["cache_key"], key)

    def test_non_blocking_by_default(self):
        key = self._submit("s3")
        result = handle_display_bitmap(cache_key=key)
        self.assertFalse(result["blocking"])

    def test_blocking_mode(self):
        key = self._submit("s4")
        set_display_confirmer(lambda: key)
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertTrue(result["blocking"])
        self.assertIn("confirmed_cache_key", result)

    def test_blocking_confirms_same_key(self):
        key = self._submit("s5")
        set_display_confirmer(lambda: key)
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertEqual(result["confirmed_cache_key"], key)

    def test_unknown_key_returns_error(self):
        result = handle_display_bitmap(cache_key="0xNONEXIST")
        self.assertFalse(result["success"])
        self.assertIn("error", result)


class SubmitBitmapHandlerTest(unittest.TestCase):

    def setUp(self):
        handlers.reset()

    def test_returns_cache_key(self):
        image_data = base64.b64encode(b"fake png data").decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("cache_key", result)
        self.assertTrue(len(result["cache_key"]) > 0)

    def test_returns_courtesy_screenshot(self):
        image_data = base64.b64encode(b"fake png data").decode()
        result = handle_submit_bitmap(image_data=image_data)
        self.assertIn("courtesy_screenshot", result)
        decoded = base64.b64decode(result["courtesy_screenshot"])
        self.assertTrue(len(decoded) > 0)

    def test_cache_key_is_hex_format(self):
        image_data = base64.b64encode(b"test image").decode()
        result = handle_submit_bitmap(image_data=image_data)
        cache_key = result["cache_key"]
        self.assertTrue(cache_key.startswith("0x"))
        int(cache_key, 16)

    def test_different_images_get_different_keys(self):
        img1 = base64.b64encode(b"image one").decode()
        img2 = base64.b64encode(b"image two").decode()
        result1 = handle_submit_bitmap(image_data=img1)
        result2 = handle_submit_bitmap(image_data=img2)
        self.assertNotEqual(result1["cache_key"], result2["cache_key"])


class GetScreenshotHandlerTest(unittest.TestCase):

    def setUp(self):
        handlers.reset()

    def test_returns_screenshot(self):
        result = handle_get_screenshot()
        self.assertIn("screenshot", result)

    def test_screenshot_is_base64_encoded(self):
        result = handle_get_screenshot()
        decoded = base64.b64decode(result["screenshot"])
        self.assertTrue(len(decoded) > 0)


class EventCallbackTest(unittest.TestCase):

    def setUp(self):
        handlers.reset()
        self.events = []
        set_event_callback(lambda *args: self.events.append(args))

    def tearDown(self):
        handlers.reset()

    def test_submit_fires_callback(self):
        img = base64.b64encode(b"test-png-data").decode()
        result = handle_submit_bitmap(image_data=img)
        self.assertEqual(len(self.events), 1)
        event_type, cache_key, image_data = self.events[0]
        self.assertEqual(event_type, "bitmap_submitted")
        self.assertEqual(cache_key, result["cache_key"])
        self.assertEqual(image_data, b"test-png-data")

    def test_display_fires_callback(self):
        img = base64.b64encode(b"test-png-data").decode()
        result = handle_submit_bitmap(image_data=img)
        self.events.clear()
        handle_display_bitmap(cache_key=result["cache_key"])
        self.assertEqual(len(self.events), 1)
        event_type, cache_key, image_data = self.events[0]
        self.assertEqual(event_type, "display_requested")
        self.assertEqual(cache_key, result["cache_key"])
        self.assertIsNone(image_data)

    def test_no_callback_doesnt_raise(self):
        handlers.reset()
        img = base64.b64encode(b"test-data").decode()
        result = handle_submit_bitmap(image_data=img)
        self.assertIn("cache_key", result)

    def test_failed_display_doesnt_fire_callback(self):
        handle_display_bitmap(cache_key="0xNONEXIST")
        callback_events = [e for e in self.events if e[0] == "display_requested"]
        self.assertEqual(len(callback_events), 0)

    def test_reset_clears_callback(self):
        handlers.reset()
        img = base64.b64encode(b"after-reset").decode()
        handle_submit_bitmap(image_data=img)
        self.assertEqual(len(self.events), 0)


if __name__ == "__main__":
    unittest.main()
