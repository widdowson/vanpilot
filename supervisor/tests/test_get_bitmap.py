"""Tests for GetBitmap and ReconcileCache RPCs with BitmapStore integration."""

import unittest

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import SyncServiceServicer
from proto.vanpilot.v1 import sync_pb2


class GetBitmapTest(unittest.TestCase):
    """Tests for the GetBitmap RPC handler (AC-7.2, AC-7.3)."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(
            self.store, bitmap_store=self.bitmap_store
        )

    def test_get_bitmap_returns_stored_data(self):
        """GetBitmap returns the bitmap data for a known key."""
        png_data = b"\x89PNG test image data"
        self.bitmap_store.put("0xCAFEBABE", png_data)

        request = sync_pb2.GetBitmapRequest(cache_key="0xCAFEBABE")
        response = self.servicer.GetBitmap(request, context=None)

        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, "0xCAFEBABE")
        self.assertEqual(response.bitmap.image_data, png_data)

    def test_get_bitmap_missing_key_returns_empty(self):
        """GetBitmap for an unknown key returns empty response."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xNONE")
        response = self.servicer.GetBitmap(request, context=None)

        self.assertFalse(response.HasField("bitmap"))

    def test_get_bitmap_marks_key_as_sent(self):
        """After GetBitmap returns data, the key is marked as sent (AC-7.3)."""
        self.bitmap_store.put("0xABCD", b"data")

        request = sync_pb2.GetBitmapRequest(cache_key="0xABCD")
        self.servicer.GetBitmap(request, context=None)

        sent = self.bitmap_store.get_sent_keys("default")
        self.assertIn("0xABCD", sent)

    def test_get_bitmap_missing_does_not_track_sent(self):
        """GetBitmap for unknown key should not track as sent."""
        request = sync_pb2.GetBitmapRequest(cache_key="0xNOPE")
        self.servicer.GetBitmap(request, context=None)

        sent = self.bitmap_store.get_sent_keys("default")
        self.assertNotIn("0xNOPE", sent)


class ReconcileCacheTest(unittest.TestCase):
    """Tests for the ReconcileCache RPC handler (AC-7.4)."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(
            self.store, bitmap_store=self.bitmap_store
        )

    def test_reconcile_returns_missing_keys(self):
        """ReconcileCache returns keys the supervisor has that client doesn't."""
        self.bitmap_store.put("0xA", b"a")
        self.bitmap_store.put("0xB", b"b")
        self.bitmap_store.put("0xC", b"c")

        request = sync_pb2.ReconcileCacheRequest(present_keys=["0xA", "0xC"])
        response = self.servicer.ReconcileCache(request, context=None)

        self.assertEqual(set(response.missing_keys), {"0xB"})

    def test_reconcile_empty_client_returns_all(self):
        """Client with no keys gets all supervisor keys as missing."""
        self.bitmap_store.put("0xA", b"a")
        self.bitmap_store.put("0xB", b"b")

        request = sync_pb2.ReconcileCacheRequest(present_keys=[])
        response = self.servicer.ReconcileCache(request, context=None)

        self.assertEqual(set(response.missing_keys), {"0xA", "0xB"})

    def test_reconcile_client_has_everything(self):
        """Client with all keys gets empty missing list."""
        self.bitmap_store.put("0xA", b"a")

        request = sync_pb2.ReconcileCacheRequest(present_keys=["0xA"])
        response = self.servicer.ReconcileCache(request, context=None)

        self.assertEqual(list(response.missing_keys), [])

    def test_reconcile_updates_sent_tracking(self):
        """After reconcile, sent keys reflect what client reported."""
        self.bitmap_store.put("0xA", b"a")
        self.bitmap_store.mark_sent("default", "0xOLD")

        request = sync_pb2.ReconcileCacheRequest(present_keys=["0xA"])
        self.servicer.ReconcileCache(request, context=None)

        sent = self.bitmap_store.get_sent_keys("default")
        self.assertEqual(sent, {"0xA"})


if __name__ == "__main__":
    unittest.main()
