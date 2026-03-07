"""Tests for thread pool concurrency fix (#57).

Verifies that 8+ concurrent blocking GetBitmap calls don't deadlock
or block other RPCs, even with a limited thread pool.
"""

import threading
import time
import unittest
from concurrent import futures

import grpc

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import SyncServiceServicer, add_sync_service_to_server
from proto.vanpilot.v1 import sync_pb2


class ThreadPoolConcurrencyTest(unittest.TestCase):
    """Blocking GetBitmap must not exhaust the thread pool."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        add_sync_service_to_server(self.server, self.store, self.bitmap_store)
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def _call_get_bitmap(self, cache_key: str, wait_ms: int = 0) -> sync_pb2.GetBitmapResponse:
        stub = self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetBitmap",
            request_serializer=sync_pb2.GetBitmapRequest.SerializeToString,
            response_deserializer=sync_pb2.GetBitmapResponse.FromString,
        )
        req = sync_pb2.GetBitmapRequest(cache_key=cache_key, wait_ms=wait_ms)
        return stub(req, timeout=5)

    def _call_get_events(self) -> sync_pb2.GetEventsResponse:
        stub = self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )
        req = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=10)
        return stub(req, timeout=5)

    def test_eight_concurrent_blocking_getbitmap_no_deadlock(self):
        """8 concurrent blocking GetBitmap calls should all complete (timeout), not deadlock."""
        results = [None] * 8
        errors = [None] * 8

        def blocking_call(idx):
            try:
                results[idx] = self._call_get_bitmap(f"0xMISS{idx}", wait_ms=500)
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=blocking_call, args=(i,)) for i in range(8)]
        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        elapsed = time.monotonic() - start

        for i, err in enumerate(errors):
            self.assertIsNone(err, f"Thread {i} raised: {err}")
        for i, resp in enumerate(results):
            self.assertIsNotNone(resp, f"Thread {i} got no response (deadlock?)")
            self.assertFalse(resp.HasField("bitmap"))

        # All 8 should complete in roughly 500ms (parallel), not 8*500ms (serial)
        self.assertLess(elapsed, 4.0, "Calls appear to have run serially — thread pool exhausted")

    def test_get_events_not_blocked_by_concurrent_getbitmap(self):
        """GetEvents should succeed even while multiple GetBitmap calls are blocking."""
        barrier = threading.Barrier(5, timeout=5)
        errors = []

        def blocking_call():
            try:
                barrier.wait()
                self._call_get_bitmap("0xBLOCK", wait_ms=2000)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=blocking_call) for _ in range(4)]
        for t in threads:
            t.start()

        # Wait for all blocking calls to be in-flight
        barrier.wait()
        time.sleep(0.1)

        # GetEvents should still work
        start = time.monotonic()
        resp = self._call_get_events()
        elapsed = time.monotonic() - start

        self.assertIsInstance(resp, sync_pb2.GetEventsResponse)
        self.assertLess(elapsed, 2.0, "GetEvents blocked — thread pool exhausted by GetBitmap")

        # Clean up
        for t in threads:
            t.join(timeout=5)
        for err in errors:
            self.assertIsNone(err)


class EventBasedWakeupTest(unittest.TestCase):
    """BitmapStore should wake blocked GetBitmap calls immediately when data arrives."""

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(self.store, self.bitmap_store)

    def test_wakes_immediately_on_put(self):
        """Blocking GetBitmap should return as soon as put() is called, not after poll interval."""
        result = [None]

        def blocking_get():
            req = sync_pb2.GetBitmapRequest(cache_key="0xWAKE", wait_ms=5000)
            result[0] = self.servicer.GetBitmap(req, context=None)

        thread = threading.Thread(target=blocking_get)
        thread.start()

        time.sleep(0.05)  # Let the blocking call start
        start = time.monotonic()
        self.bitmap_store.put("0xWAKE", b"wakeup-data")
        thread.join(timeout=3)
        elapsed = time.monotonic() - start

        self.assertIsNotNone(result[0])
        self.assertTrue(result[0].HasField("bitmap"))
        # Should wake up nearly instantly, well under the poll interval
        self.assertLess(elapsed, 0.5)


if __name__ == "__main__":
    unittest.main()
