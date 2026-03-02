"""Tests for async (non-blocking / blocking with wait_ms) GetBitmap RPC (#57).

Covers:
  (a) blocking fetch when cached — returns data immediately
  (b) non-blocking fetch when cached — returns data immediately
  (c) non-blocking fetch when NOT cached — returns empty immediately
  (d) blocking fetch, bitmap arrives within deadline — returns data
  (e) blocking fetch, bitmap never arrives — times out, returns empty
"""

import threading
import time
import unittest

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import SyncServiceServicer
from proto.vanpilot.v1 import sync_pb2


class GetBitmapAsyncTest(unittest.TestCase):
    """Tests for GetBitmap with wait_ms parameter (#57)."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(
            self.store, bitmap_store=self.bitmap_store
        )

    # ---- (a) blocking fetch when cached ----

    def test_blocking_cached_returns_data_immediately(self):
        """wait_ms > 0 with cached bitmap returns data without waiting."""
        self.bitmap_store.put("0xCACHED", b"\x89PNG cached")

        request = sync_pb2.GetBitmapRequest(cache_key="0xCACHED", wait_ms=5000)
        start = time.monotonic()
        response = self.servicer.GetBitmap(request, context=None)
        elapsed = time.monotonic() - start

        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, "0xCACHED")
        self.assertEqual(response.bitmap.image_data, b"\x89PNG cached")
        # Should return nearly instantly, not wait the full 5 seconds
        self.assertLess(elapsed, 1.0)

    # ---- (b) non-blocking fetch when cached ----

    def test_nonblocking_cached_returns_data(self):
        """wait_ms=0 with cached bitmap returns data immediately."""
        self.bitmap_store.put("0xFAST", b"\x89PNG fast")

        request = sync_pb2.GetBitmapRequest(cache_key="0xFAST", wait_ms=0)
        response = self.servicer.GetBitmap(request, context=None)

        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, "0xFAST")
        self.assertEqual(response.bitmap.image_data, b"\x89PNG fast")

    # ---- (c) non-blocking fetch when NOT cached ----

    def test_nonblocking_missing_returns_empty_immediately(self):
        """wait_ms=0 with missing bitmap returns empty response immediately."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xMISSING", wait_ms=0)
        start = time.monotonic()
        response = self.servicer.GetBitmap(request, context=None)
        elapsed = time.monotonic() - start

        self.assertFalse(response.HasField("bitmap"))
        self.assertLess(elapsed, 0.1)

    def test_default_wait_ms_missing_returns_empty(self):
        """Default wait_ms (0) with missing bitmap returns empty (backward compat)."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xGONE")
        response = self.servicer.GetBitmap(request, context=None)

        self.assertFalse(response.HasField("bitmap"))

    # ---- (d) blocking fetch, bitmap arrives within deadline ----

    def test_blocking_waits_for_bitmap_to_arrive(self):
        """wait_ms > 0 polls until bitmap is added to store, then returns it."""
        png_data = b"\x89PNG arrived"

        def add_bitmap_later():
            time.sleep(0.15)
            self.bitmap_store.put("0xLATE", png_data)

        thread = threading.Thread(target=add_bitmap_later)
        thread.start()

        request = sync_pb2.GetBitmapRequest(cache_key="0xLATE", wait_ms=2000)
        start = time.monotonic()
        response = self.servicer.GetBitmap(request, context=None)
        elapsed = time.monotonic() - start

        thread.join()

        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, "0xLATE")
        self.assertEqual(response.bitmap.image_data, png_data)
        # Should have waited ~150ms, not the full 2 seconds
        self.assertGreater(elapsed, 0.1)
        self.assertLess(elapsed, 1.5)

    # ---- (e) blocking fetch, bitmap never arrives ----

    def test_blocking_times_out_returns_empty(self):
        """wait_ms > 0 with bitmap that never arrives returns empty after timeout."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xNEVER", wait_ms=200)
        start = time.monotonic()
        response = self.servicer.GetBitmap(request, context=None)
        elapsed = time.monotonic() - start

        self.assertFalse(response.HasField("bitmap"))
        # Should have waited approximately 200ms
        self.assertGreater(elapsed, 0.15)
        self.assertLess(elapsed, 1.0)

    # ---- sent-tracking with wait_ms ----

    def test_blocking_marks_sent_on_success(self):
        """Bitmap returned after blocking wait is marked as sent (AC-7.3)."""
        self.bitmap_store.put("0xTRACK", b"data")

        request = sync_pb2.GetBitmapRequest(cache_key="0xTRACK", wait_ms=100)
        self.servicer.GetBitmap(request, context=None)

        sent = self.bitmap_store.get_sent_keys("default")
        self.assertIn("0xTRACK", sent)

    def test_blocking_timeout_does_not_mark_sent(self):
        """Bitmap that times out should not be marked as sent."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xNOPE", wait_ms=100)
        self.servicer.GetBitmap(request, context=None)

        sent = self.bitmap_store.get_sent_keys("default")
        self.assertNotIn("0xNOPE", sent)


if __name__ == "__main__":
    unittest.main()
