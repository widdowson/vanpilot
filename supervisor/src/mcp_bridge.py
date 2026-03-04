"""Bridge between MCP handler events and the supervisor's gRPC event store.

When the MCP server processes submit_bitmap or display_bitmap tool calls,
the bridge translates those into gRPC events (BitmapPayload, DisplayCommand)
and adds them to the EventStore for the Android app to pull via GetEvents.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from supervisor.src.bitmap_cache_tracker import BitmapCacheTracker
from supervisor.src.event_store import EventStore
from proto.vanpilot.v1 import sync_pb2

if TYPE_CHECKING:
    from supervisor.src.android_app_client import AndroidAppClient


class BitmapStore:
    """Thread-safe store for bitmap data, keyed by cache key.

    Used by GetBitmap to serve bitmaps that the Android app doesn't have cached.
    Delegates sent-tracking (AC-7.3) and cache reconciliation (AC-7.4) to a
    BitmapCacheTracker instance.
    """

    def __init__(self, tracker: BitmapCacheTracker | None = None) -> None:
        self._tracker = tracker or BitmapCacheTracker()

    def put(self, cache_key: str, data: bytes) -> None:
        self._tracker.store_bitmap(cache_key, data)

    def get(self, cache_key: str) -> bytes | None:
        return self._tracker.get_bitmap(cache_key)

    def has(self, cache_key: str) -> bool:
        return self._tracker.has_bitmap(cache_key)

    def all_keys(self) -> set[str]:
        """Return all stored cache keys."""
        return self._tracker.all_keys()

    def mark_sent(self, client_id: str, cache_key: str) -> None:
        """Record that a cache key has been sent to a client (AC-7.3)."""
        self._tracker.mark_sent(client_id, cache_key)

    def get_sent_keys(self, client_id: str) -> set[str]:
        """Return the set of cache keys sent to a client."""
        return self._tracker.get_sent_keys(client_id)

    def clear_client(self, client_id: str) -> None:
        """Remove all tracking for a client (e.g., on disconnect)."""
        self._tracker.clear_client(client_id)

    def reconcile(self, client_id: str, present_keys: set[str]) -> set[str]:
        """Reconcile cache state with a client on reconnection (AC-7.4).

        Args:
            client_id: Identifier for the reconnecting client.
            present_keys: Cache keys the client reports having.

        Returns:
            Set of cache keys the supervisor has that the client is missing.
        """
        return self._tracker.reconcile(client_id, present_keys)


def _current_time_ms() -> int:
    """Return the current time in milliseconds since epoch."""
    return int(time.time() * 1000)


class McpBridge:
    """Converts MCP display tool events into gRPC events.

    Call on_bitmap_submitted when the MCP handles submit_bitmap.
    Call on_display_requested when the MCP handles display_bitmap.

    When constructed with an optional app_client, registers a display
    confirmer with the MCP handlers so that blocking=true can poll the
    Android app's current display state (AC-6.3).
    """

    def __init__(
        self,
        event_store: EventStore,
        bitmap_store: BitmapStore,
        app_client: AndroidAppClient | None = None,
    ) -> None:
        self._event_store = event_store
        self._bitmap_store = bitmap_store
        self._app_client = app_client

        if app_client is not None:
            from mcp.src.handlers import set_display_confirmer

            def _confirmer() -> str:
                try:
                    return app_client.get_current_display()
                except Exception:
                    return ""

            set_display_confirmer(_confirmer)

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
