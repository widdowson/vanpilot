"""Tests for the in-memory event store."""

import unittest

from supervisor.src.event_store import EventStore
from proto.vanpilot.v1 import sync_pb2


class EventStoreTest(unittest.TestCase):

    def test_initial_hardcoded_events(self):
        """The store should be seeded with hardcoded events on creation."""
        store = EventStore()
        events = store.get_events(since_timestamp_ms=0, max_count=100)
        self.assertGreater(len(events), 0)

    def test_all_events_have_timestamps(self):
        """Every event must have a positive timestamp."""
        store = EventStore()
        events = store.get_events(since_timestamp_ms=0, max_count=100)
        for event in events:
            self.assertGreater(event.timestamp_ms, 0)

    def test_events_sorted_by_timestamp(self):
        """Events should be returned in chronological order."""
        store = EventStore()
        events = store.get_events(since_timestamp_ms=0, max_count=100)
        timestamps = [e.timestamp_ms for e in events]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_since_timestamp_filters(self):
        """Only events at or after since_timestamp_ms should be returned."""
        store = EventStore()
        all_events = store.get_events(since_timestamp_ms=0, max_count=100)
        if len(all_events) < 2:
            self.skipTest("Need at least 2 events to test filtering")
        mid_ts = all_events[1].timestamp_ms
        filtered = store.get_events(since_timestamp_ms=mid_ts, max_count=100)
        for event in filtered:
            self.assertGreaterEqual(event.timestamp_ms, mid_ts)
        self.assertLess(len(filtered), len(all_events))

    def test_max_count_limits_results(self):
        """Should return at most max_count events."""
        store = EventStore()
        events = store.get_events(since_timestamp_ms=0, max_count=1)
        self.assertEqual(len(events), 1)

    def test_hardcoded_events_have_text_messages(self):
        """At least some hardcoded events should be TextMessage type."""
        store = EventStore()
        events = store.get_events(since_timestamp_ms=0, max_count=100)
        text_events = [
            e for e in events if e.WhichOneof("payload") == "text_message"
        ]
        self.assertGreater(len(text_events), 0)

    def test_add_event(self):
        """Should be able to add new events to the store."""
        store = EventStore()
        initial_count = len(store.get_events(since_timestamp_ms=0, max_count=1000))
        event = sync_pb2.Event(
            timestamp_ms=99999999,
            text_message=sync_pb2.TextMessage(
                agent_id="test",
                content="test event",
            ),
        )
        store.add_event(event)
        new_count = len(store.get_events(since_timestamp_ms=0, max_count=1000))
        self.assertEqual(new_count, initial_count + 1)


if __name__ == "__main__":
    unittest.main()
