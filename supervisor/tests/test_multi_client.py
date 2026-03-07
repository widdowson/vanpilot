"""Tests for multi-client support in SyncService.

Each Android client should get independent sent-tracking and cache
reconciliation, identified by its gRPC peer address.
"""

import unittest
from unittest.mock import MagicMock

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import SyncServiceServicer
from proto.vanpilot.v1 import sync_pb2


def _make_context(peer: str) -> MagicMock:
    """Create a mock gRPC context with a given peer address."""
    ctx = MagicMock()
    ctx.peer.return_value = peer
    ctx.is_active.return_value = True
    return ctx


class MultiClientGetBitmapTest(unittest.TestCase):
    """GetBitmap should track sent bitmaps per-client, not globally."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(self.store, self.bitmap_store)
        self.bitmap_store.put("0xSHARED", b"shared-data")

    def test_different_clients_get_independent_sent_tracking(self):
        """Two clients fetching the same bitmap should each get their own sent record."""
        ctx_a = _make_context("ipv4:10.0.0.1:12345")
        ctx_b = _make_context("ipv4:10.0.0.2:54321")

        req = sync_pb2.GetBitmapRequest(cache_key="0xSHARED")
        self.servicer.GetBitmap(req, ctx_a)
        self.servicer.GetBitmap(req, ctx_b)

        sent_a = self.bitmap_store.get_sent_keys("ipv4:10.0.0.1:12345")
        sent_b = self.bitmap_store.get_sent_keys("ipv4:10.0.0.2:54321")
        self.assertIn("0xSHARED", sent_a)
        self.assertIn("0xSHARED", sent_b)

    def test_client_sent_tracking_does_not_leak(self):
        """One client's sent keys should not appear in another client's set."""
        ctx_a = _make_context("ipv4:10.0.0.1:12345")
        self.bitmap_store.put("0xONLY_A", b"only-a")

        req = sync_pb2.GetBitmapRequest(cache_key="0xONLY_A")
        self.servicer.GetBitmap(req, ctx_a)

        sent_b = self.bitmap_store.get_sent_keys("ipv4:10.0.0.2:54321")
        self.assertNotIn("0xONLY_A", sent_b)

    def test_none_context_uses_fallback_client_id(self):
        """When context is None (unit tests), should still work with a fallback ID."""
        req = sync_pb2.GetBitmapRequest(cache_key="0xSHARED")
        response = self.servicer.GetBitmap(req, context=None)
        self.assertTrue(response.HasField("bitmap"))


class MultiClientReconcileCacheTest(unittest.TestCase):
    """ReconcileCache should work independently per client."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(self.store, self.bitmap_store)
        self.bitmap_store.put("0xA", b"a")
        self.bitmap_store.put("0xB", b"b")
        self.bitmap_store.put("0xC", b"c")

    def test_reconcile_uses_peer_as_client_id(self):
        """ReconcileCache should use the gRPC peer address, not a hardcoded default."""
        ctx = _make_context("ipv4:10.0.0.1:12345")

        req = sync_pb2.ReconcileCacheRequest(present_keys=["0xA"])
        resp = self.servicer.ReconcileCache(req, ctx)

        self.assertIn("0xB", resp.missing_keys)
        self.assertIn("0xC", resp.missing_keys)
        self.assertNotIn("0xA", resp.missing_keys)

    def test_two_clients_reconcile_independently(self):
        """Each client reconciles against its own state."""
        ctx_a = _make_context("ipv4:10.0.0.1:12345")
        ctx_b = _make_context("ipv4:10.0.0.2:54321")

        req_a = sync_pb2.ReconcileCacheRequest(present_keys=["0xA", "0xB"])
        req_b = sync_pb2.ReconcileCacheRequest(present_keys=["0xC"])

        resp_a = self.servicer.ReconcileCache(req_a, ctx_a)
        resp_b = self.servicer.ReconcileCache(req_b, ctx_b)

        self.assertEqual(set(resp_a.missing_keys), {"0xC"})
        self.assertEqual(set(resp_b.missing_keys), {"0xA", "0xB"})


if __name__ == "__main__":
    unittest.main()
