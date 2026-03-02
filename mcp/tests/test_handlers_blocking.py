"""Tests for display_bitmap(blocking=true) polling behavior (AC-6.3).

When blocking=true, handle_display_bitmap must poll until the Android app
confirms it is displaying the requested cache key, or timeout with an error.
"""

import base64
import unittest
import threading
import time

import mcp.src.handlers as handlers
from mcp.src.handlers import (
    handle_display_bitmap,
    handle_submit_bitmap,
    set_display_confirmer,
)


class BlockingDisplayTest(unittest.TestCase):
    """Tests that blocking=true polls for app confirmation."""

    def setUp(self):
        handlers.reset()

    def _submit(self, tag: str) -> str:
        img = base64.b64encode(b"png-data-" + tag.encode()).decode()
        return handle_submit_bitmap(image_data=img)["cache_key"]

    def test_blocking_polls_confirmer_until_match(self):
        """blocking=true should call the confirmer until it returns the key."""
        key = self._submit("b1")
        call_count = 0

        def confirmer():
            nonlocal call_count
            call_count += 1
            # Confirm on the 3rd poll
            if call_count >= 3:
                return key
            return ""

        set_display_confirmer(confirmer)
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["confirmed_cache_key"], key)
        self.assertGreaterEqual(call_count, 3)

    def test_blocking_returns_immediately_when_already_displayed(self):
        """If confirmer returns the key on first call, return immediately."""
        key = self._submit("b2")
        set_display_confirmer(lambda: key)
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["confirmed_cache_key"], key)

    def test_blocking_timeout_returns_error(self):
        """If confirmer never returns the key, timeout with an error."""
        key = self._submit("b3")
        set_display_confirmer(lambda: "")  # Never confirms

        result = handle_display_bitmap(
            cache_key=key, blocking=True, timeout_seconds=0.3
        )
        self.assertFalse(result["success"])
        self.assertIn("timeout", result["error"].lower())

    def test_blocking_without_confirmer_returns_error(self):
        """If no confirmer is set, blocking=true should return an error."""
        key = self._submit("b4")
        # No confirmer set (default after reset)
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_non_blocking_ignores_confirmer(self):
        """blocking=false should not call the confirmer at all."""
        key = self._submit("b5")
        called = False

        def confirmer():
            nonlocal called
            called = True
            return key

        set_display_confirmer(confirmer)
        result = handle_display_bitmap(cache_key=key, blocking=False)
        self.assertTrue(result["success"])
        self.assertFalse(called)

    def test_blocking_still_fires_event_callback(self):
        """blocking=true should still fire the display_requested event."""
        key = self._submit("b6")
        events = []
        handlers.set_event_callback(lambda *args: events.append(args))
        set_display_confirmer(lambda: key)

        handle_display_bitmap(cache_key=key, blocking=True)
        display_events = [e for e in events if e[0] == "display_requested"]
        self.assertEqual(len(display_events), 1)

    def test_blocking_unknown_key_returns_error_without_polling(self):
        """An unknown cache key should fail immediately, not poll."""
        called = False

        def confirmer():
            nonlocal called
            called = True
            return ""

        set_display_confirmer(confirmer)
        result = handle_display_bitmap(cache_key="0xNONEXIST", blocking=True)
        self.assertFalse(result["success"])
        self.assertFalse(called)

    def test_reset_clears_confirmer(self):
        """reset() should clear the display confirmer."""
        set_display_confirmer(lambda: "some-key")
        handlers.reset()
        key = self._submit("b7")
        result = handle_display_bitmap(cache_key=key, blocking=True)
        self.assertFalse(result["success"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
