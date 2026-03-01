"""Tests for flipping between cached images without retransmission (AC-7.5).

Verifies that the lead agent can display image A, switch to B, and switch
back to A without needing to re-submit either bitmap.
"""

import base64
import unittest

import mcp.src.handlers as handlers
from mcp.src.handlers import handle_submit_bitmap, handle_display_bitmap


class FlipBetweenCachedImagesTest(unittest.TestCase):
    """Tests for flipping between cached images (AC-7.5)."""

    def setUp(self):
        handlers.reset()

    def test_flip_between_two_images(self):
        """Can display A, then B, then A again without re-submitting."""
        raw_a = b"image-A-png-data"
        raw_b = b"image-B-png-data"
        key_a = handle_submit_bitmap(
            image_data=base64.b64encode(raw_a).decode()
        )["cache_key"]
        key_b = handle_submit_bitmap(
            image_data=base64.b64encode(raw_b).decode()
        )["cache_key"]

        # Display A
        result = handle_display_bitmap(cache_key=key_a)
        self.assertTrue(result["success"])

        # Flip to B
        result = handle_display_bitmap(cache_key=key_b)
        self.assertTrue(result["success"])

        # Flip back to A (no retransmission needed)
        result = handle_display_bitmap(cache_key=key_a)
        self.assertTrue(result["success"])
        self.assertEqual(result["cache_key"], key_a)

    def test_flip_many_times(self):
        """Rapidly flip through multiple cached images."""
        keys = []
        for i in range(5):
            raw = f"img-{i}".encode()
            key = handle_submit_bitmap(
                image_data=base64.b64encode(raw).decode()
            )["cache_key"]
            keys.append(key)

        # Flip through all, then back
        for key in keys + list(reversed(keys)):
            result = handle_display_bitmap(cache_key=key)
            self.assertTrue(result["success"])

    def test_display_after_submit_requires_no_retransmission(self):
        """Once submitted, a bitmap can be displayed any number of times."""
        raw = b"one-time-submit"
        key = handle_submit_bitmap(
            image_data=base64.b64encode(raw).decode()
        )["cache_key"]

        for _ in range(10):
            result = handle_display_bitmap(cache_key=key)
            self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
