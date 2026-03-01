"""Bridge between MCP handler events and the supervisor's gRPC event store.

When the MCP server processes submit_bitmap or display_bitmap tool calls,
the bridge translates those into gRPC events (BitmapPayload, DisplayCommand)
and adds them to the EventStore for the Android app to pull via GetEvents.
"""

import threading
import time

from supervisor.src.event_store import EventStore
from proto.vanpilot.v1 import sync_pb2


class BitmapStore:
    """Thread-safe store for bitmap data, keyed by cache key.

    Used by GetBitmap to serve bitmaps that the Android app doesn't have cached.
    Also tracks which keys have been sent to each client (AC-7.3) and supports
    cache reconciliation on reconnection (AC-7.4).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, bytes] = {}
        # client_id -> set of cache keys sent to that client
        self._sent: dict[str, set[str]] = {}

    def put(self, cache_key: str, data: bytes) -> None:
        with self._lock:
            self._cache[cache_key] = data

    def get(self, cache_key: str) -> bytes | None:
        with self._lock:
            return self._cache.get(cache_key)

    def has(self, cache_key: str) -> bool:
        with self._lock:
            return cache_key in self._cache

    def all_keys(self) -> set[str]:
        """Return all stored cache keys."""
        with self._lock:
            return set(self._cache.keys())

    def mark_sent(self, client_id: str, cache_key: str) -> None:
        """Record that a cache key has been sent to a client (AC-7.3)."""
        with self._lock:
            if client_id not in self._sent:
                self._sent[client_id] = set()
            self._sent[client_id].add(cache_key)

    def get_sent_keys(self, client_id: str) -> set[str]:
        """Return the set of cache keys sent to a client."""
        with self._lock:
            return set(self._sent.get(client_id, set()))

    def clear_client(self, client_id: str) -> None:
        """Remove all tracking for a client (e.g., on disconnect)."""
        with self._lock:
            self._sent.pop(client_id, None)

    def reconcile(self, client_id: str, present_keys: set[str]) -> set[str]:
        """Reconcile cache state with a client on reconnection (AC-7.4).

        Args:
            client_id: Identifier for the reconnecting client.
            present_keys: Cache keys the client reports having.

        Returns:
            Set of cache keys the supervisor has that the client is missing.
        """
        with self._lock:
            self._sent[client_id] = set(present_keys)
            return set(self._cache.keys()) - present_keys


def _current_time_ms() -> int:
    """Return the current time in milliseconds since epoch."""
    return int(time.time() * 1000)


class McpBridge:
    """Converts MCP display tool events into gRPC events.

    Call on_bitmap_submitted when the MCP handles submit_bitmap.
    Call on_display_requested when the MCP handles display_bitmap.
    """

    def __init__(self, event_store: EventStore, bitmap_store: BitmapStore) -> None:
        self._event_store = event_store
        self._bitmap_store = bitmap_store

    def on_bitmap_submitted(self, cache_key: str, image_data: bytes) -> None:
        """A new bitmap was submitted via the MCP. Create a BitmapPayload event."""
        self._bitmap_store.put(cache_key, image_data)
        event = sync_pb2.Event(
            timestamp_ms=_current_time_ms(),
            bitmap_payload=sync_pb2.BitmapPayload(
                cache_key=cache_key,
                image_data=image_data,
            ),
        )
        self._event_store.add_event(event)

    def on_display_requested(self, cache_key: str) -> None:
        """A display command was issued via the MCP. Create a DisplayCommand event."""
        event = sync_pb2.Event(
            timestamp_ms=_current_time_ms(),
            display_command=sync_pb2.DisplayCommand(
                cache_key=cache_key,
            ),
        )
        self._event_store.add_event(event)
