"""Tests for the MCP-to-supervisor bridge."""

import unittest
import time

from supervisor.src.mcp_bridge import McpBridge, BitmapStore
from supervisor.src.event_store import EventStore
from proto.vanpilot.v1 import sync_pb2


class BitmapStoreTest(unittest.TestCase):
    """Tests for the thread-safe bitmap store."""

    def test_put_and_get(self):
        store = BitmapStore()
        store.put("0xDEADBEEF", b"png-data")
        self.assertEqual(store.get("0xDEADBEEF"), b"png-data")

    def test_get_missing_returns_none(self):
        store = BitmapStore()
        self.assertIsNone(store.get("0xNONEXIST"))

    def test_has_key(self):
        store = BitmapStore()
        self.assertFalse(store.has("0xDEADBEEF"))
        store.put("0xDEADBEEF", b"data")
        self.assertTrue(store.has("0xDEADBEEF"))

    def test_overwrite(self):
        store = BitmapStore()
        store.put("0xAABBCCDD", b"old")
        store.put("0xAABBCCDD", b"new")
        self.assertEqual(store.get("0xAABBCCDD"), b"new")


class McpBridgeTest(unittest.TestCase):
    """Tests for the MCP bridge that converts MCP events to gRPC events."""

    def setUp(self):
        self.event_store = EventStore()
        self.bitmap_store = BitmapStore()
        self.bridge = McpBridge(self.event_store, self.bitmap_store)

    def test_on_bitmap_submitted_creates_event(self):
        """submit_bitmap should create a BitmapPayload event in the store."""
        self.bridge.on_bitmap_submitted("0xABCD1234", b"fake-png-data")

        # Get all events (including hardcoded seed events)
        events = self.event_store.get_events(since_timestamp_ms=0, max_count=100)
        bitmap_events = [
            e for e in events if e.WhichOneof("payload") == "bitmap_payload"
        ]
        self.assertEqual(len(bitmap_events), 1)
        self.assertEqual(bitmap_events[0].bitmap_payload.cache_key, "0xABCD1234")
        self.assertEqual(bitmap_events[0].bitmap_payload.image_data, b"fake-png-data")

    def test_on_bitmap_submitted_stores_in_bitmap_store(self):
        """submit_bitmap should also store the bitmap for GetBitmap lookups."""
        self.bridge.on_bitmap_submitted("0xABCD1234", b"fake-png-data")
        self.assertEqual(self.bitmap_store.get("0xABCD1234"), b"fake-png-data")

    def test_on_display_requested_creates_event(self):
        """display_bitmap should create a DisplayCommand event in the store."""
        self.bridge.on_display_requested("0xABCD1234")

        events = self.event_store.get_events(since_timestamp_ms=0, max_count=100)
        display_events = [
            e for e in events if e.WhichOneof("payload") == "display_command"
        ]
        self.assertEqual(len(display_events), 1)
        self.assertEqual(display_events[0].display_command.cache_key, "0xABCD1234")

    def test_events_have_positive_timestamps(self):
        """Bridge-created events should have realistic timestamps."""
        self.bridge.on_bitmap_submitted("0xA", b"data")
        self.bridge.on_display_requested("0xA")

        events = self.event_store.get_events(since_timestamp_ms=0, max_count=100)
        for event in events:
            self.assertGreater(event.timestamp_ms, 0)

    def test_multiple_submits(self):
        """Multiple submit_bitmap calls should create multiple events."""
        self.bridge.on_bitmap_submitted("0xAAAAAAAA", b"data-a")
        self.bridge.on_bitmap_submitted("0xBBBBBBBB", b"data-b")

        events = self.event_store.get_events(since_timestamp_ms=0, max_count=100)
        bitmap_events = [
            e for e in events if e.WhichOneof("payload") == "bitmap_payload"
        ]
        self.assertEqual(len(bitmap_events), 2)
        keys = {e.bitmap_payload.cache_key for e in bitmap_events}
        self.assertEqual(keys, {"0xAAAAAAAA", "0xBBBBBBBB"})

    def test_display_after_submit(self):
        """Full flow: submit then display should create both event types."""
        self.bridge.on_bitmap_submitted("0xCAFEBABE", b"image-bytes")
        self.bridge.on_display_requested("0xCAFEBABE")

        events = self.event_store.get_events(since_timestamp_ms=0, max_count=100)
        bitmap_events = [
            e for e in events if e.WhichOneof("payload") == "bitmap_payload"
        ]
        display_events = [
            e for e in events if e.WhichOneof("payload") == "display_command"
        ]
        self.assertEqual(len(bitmap_events), 1)
        self.assertEqual(len(display_events), 1)


if __name__ == "__main__":
    unittest.main()
