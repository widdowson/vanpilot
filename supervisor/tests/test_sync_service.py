"""Tests for the SyncService gRPC implementation."""

import unittest
import grpc
from concurrent import futures

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore
from supervisor.src.sync_service import SyncServiceServicer, add_sync_service_to_server
from proto.vanpilot.v1 import sync_pb2


class SyncServiceServicerTest(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()
        self.servicer = SyncServiceServicer(self.store)

    def test_get_events_returns_response(self):
        request = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=10)
        response = self.servicer.GetEvents(request, context=None)
        self.assertIsInstance(response, sync_pb2.GetEventsResponse)

    def test_get_events_returns_hardcoded_events(self):
        request = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=100)
        response = self.servicer.GetEvents(request, context=None)
        self.assertGreater(len(response.events), 0)

    def test_get_events_respects_max_count(self):
        request = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=1)
        response = self.servicer.GetEvents(request, context=None)
        self.assertEqual(len(response.events), 1)

    def test_get_events_respects_since_timestamp(self):
        all_req = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=100)
        all_resp = self.servicer.GetEvents(all_req, context=None)
        if len(all_resp.events) < 2:
            self.skipTest("Need at least 2 events")
        mid_ts = all_resp.events[1].timestamp_ms
        filtered_req = sync_pb2.GetEventsRequest(since_timestamp_ms=mid_ts, max_count=100)
        filtered_resp = self.servicer.GetEvents(filtered_req, context=None)
        self.assertLess(len(filtered_resp.events), len(all_resp.events))
        for event in filtered_resp.events:
            self.assertGreaterEqual(event.timestamp_ms, mid_ts)


class GetBitmapTest(unittest.TestCase):

    def setUp(self):
        self.store = EventStore()
        self.bitmap_store = BitmapStore()
        self.servicer = SyncServiceServicer(self.store, self.bitmap_store)

    def test_get_bitmap_found(self):
        self.bitmap_store.put("0xABCD1234", b"fake-png-data")
        request = sync_pb2.GetBitmapRequest(cache_key="0xABCD1234")
        response = self.servicer.GetBitmap(request, context=None)
        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, "0xABCD1234")
        self.assertEqual(response.bitmap.image_data, b"fake-png-data")

    def test_get_bitmap_not_found(self):
        request = sync_pb2.GetBitmapRequest(cache_key="0xNONEXIST")
        response = self.servicer.GetBitmap(request, context=None)
        self.assertFalse(response.HasField("bitmap"))

    def test_get_bitmap_after_put(self):
        self.bitmap_store.put("0x11223344", b"image-data-1")
        self.bitmap_store.put("0x55667788", b"image-data-2")
        resp1 = self.servicer.GetBitmap(sync_pb2.GetBitmapRequest(cache_key="0x11223344"), context=None)
        resp2 = self.servicer.GetBitmap(sync_pb2.GetBitmapRequest(cache_key="0x55667788"), context=None)
        self.assertEqual(resp1.bitmap.image_data, b"image-data-1")
        self.assertEqual(resp2.bitmap.image_data, b"image-data-2")


class SyncServiceIntegrationTest(unittest.TestCase):

    def setUp(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        store = EventStore()
        bitmap_store = BitmapStore()
        add_sync_service_to_server(self.server, store, bitmap_store)
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def test_get_events_over_grpc(self):
        request = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=10)
        response = self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )(request)
        self.assertIsInstance(response, sync_pb2.GetEventsResponse)
        self.assertGreater(len(response.events), 0)

    def test_get_events_unknown_method_fails(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self.channel.unary_unary(
                "/vanpilot.v1.SyncService/NonExistent",
                request_serializer=lambda x: b"",
                response_deserializer=lambda x: x,
            )(b"")
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.UNIMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
