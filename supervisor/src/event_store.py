"""In-memory event store with hardcoded seed events."""

import threading
from typing import List

from proto.vanpilot.v1 import sync_pb2


def _make_hardcoded_events() -> List[sync_pb2.Event]:
    """Create the initial set of hardcoded events for the skeleton."""
    return [
        sync_pb2.Event(
            timestamp_ms=1000,
            text_message=sync_pb2.TextMessage(
                agent_id="lead",
                content="VanPilot supervisor online. Awaiting instructions.",
            ),
        ),
        sync_pb2.Event(
            timestamp_ms=2000,
            text_message=sync_pb2.TextMessage(
                agent_id="lead",
                content="Agent team initialized with 1 member.",
            ),
        ),
        sync_pb2.Event(
            timestamp_ms=3000,
            watchdog_timeout=sync_pb2.WatchdogTimeout(
                agent_id="researcher",
                silent_duration_ms=30000,
            ),
        ),
    ]


class EventStore:
    """Thread-safe in-memory store for supervisor events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[sync_pb2.Event] = _make_hardcoded_events()

    def get_events(
        self, since_timestamp_ms: int, max_count: int
    ) -> List[sync_pb2.Event]:
        """Return events at or after since_timestamp_ms, up to max_count."""
        with self._lock:
            filtered = [
                e for e in self._events if e.timestamp_ms >= since_timestamp_ms
            ]
            filtered.sort(key=lambda e: e.timestamp_ms)
            return filtered[:max_count]

    def add_event(self, event: sync_pb2.Event) -> None:
        """Add a new event to the store."""
        with self._lock:
            self._events.append(event)
