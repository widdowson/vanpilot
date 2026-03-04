"""Tracks bitmap cache state across the supervisor and connected clients.

The BitmapCacheTracker stores all bitmaps submitted via the MCP and tracks
which cache keys have been sent to each connected Android app client.
On reconnection, it supports cache reconciliation so the client can learn
what it's missing without full retransmission.

BitmapStore (in mcp_bridge.py) delegates all storage and sent-tracking to
a BitmapCacheTracker instance via composition.
"""

from __future__ import annotations

import threading
from typing import Optional


class BitmapCacheTracker:
    """Thread-safe bitmap cache with per-client sent-key tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # cache_key -> raw PNG bytes
        self._bitmaps: dict[str, bytes] = {}
        # client_id -> set of cache keys sent to that client
        self._sent: dict[str, set[str]] = {}

    def store_bitmap(self, cache_key: str, image_data: bytes) -> None:
        """Store a bitmap by cache key."""
        with self._lock:
            self._bitmaps[cache_key] = image_data

    def get_bitmap(self, cache_key: str) -> Optional[bytes]:
        """Retrieve a bitmap by cache key, or None if not found."""
        with self._lock:
            return self._bitmaps.get(cache_key)

    def has_bitmap(self, cache_key: str) -> bool:
        """Check if a bitmap exists for the given cache key."""
        with self._lock:
            return cache_key in self._bitmaps

    def all_keys(self) -> set[str]:
        """Return all stored cache keys."""
        with self._lock:
            return set(self._bitmaps.keys())

    def mark_sent(self, client_id: str, cache_key: str) -> None:
        """Record that a cache key has been sent to a client."""
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
        """Reconcile cache state with a client on reconnection.

        Args:
            client_id: Identifier for the reconnecting client.
            present_keys: Cache keys the client reports having.

        Returns:
            Set of cache keys the supervisor has that the client is missing.
        """
        with self._lock:
            # Update sent tracking to reflect what client actually has
            self._sent[client_id] = set(present_keys)
            # Missing = supervisor keys minus client keys
            return set(self._bitmaps.keys()) - present_keys
