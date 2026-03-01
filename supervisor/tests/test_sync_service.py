"""Tests for the SyncService gRPC implementation."""

import unittest
import grpc
from concurrent import futures

from supervisor.src.event_store import EventStore
from supervisor.src.sync_service import SyncServiceServicer, add_sync_service_to_server
from proto.vanpilot.v1 import sync_pb2


class SyncServiceServicerTest(unittest.TestCase):
    """Unit tests for SyncServiceServicer without a real gRPC server."""

    def setUp(self):
        self.store = EventStore()
        self.servicer = SyncServiceServicer(self.store)

    def test_get_events_returns_response(self):
        """GetEvents should return a GetEventsResponse."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=0,
            max_count=10,
        )
        response = self.servicer.GetEvents(request, context=None)
        self.assertIsInstance(response, sync_pb2.GetEventsResponse)

    def test_get_events_returns_hardcoded_events(self):
        """GetEvents with timestamp 0 should return the hardcoded events."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=0,
            max_count=100,
        )
        response = self.servicer.GetEvents(request, context=None)
        self.assertGreater(len(response.events), 0)

    def test_get_events_respects_max_count(self):
        """GetEvents should not return more than max_count events."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=0,
            max_count=1,
        )
        response = self.servicer.GetEvents(request, context=None)
        self.assertEqual(len(response.events), 1)

    def test_get_events_respects_since_timestamp(self):
        """GetEvents should filter by since_timestamp_ms."""
        # First get all events
        all_req = sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=100)
        all_resp = self.servicer.GetEvents(all_req, context=None)
        if len(all_resp.events) < 2:
            self.skipTest("Need at least 2 events")
        # Filter from the second event's timestamp
        mid_ts = all_resp.events[1].timestamp_ms
        filtered_req = sync_pb2.GetEventsRequest(
            since_timestamp_ms=mid_ts, max_count=100
        )
        filtered_resp = self.servicer.GetEvents(filtered_req, context=None)
        self.assertLess(len(filtered_resp.events), len(all_resp.events))
        for event in filtered_resp.events:
            self.assertGreaterEqual(event.timestamp_ms, mid_ts)


class SyncServiceIntegrationTest(unittest.TestCase):
    """Integration test that starts a real gRPC server and client."""

    def setUp(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        store = EventStore()
        add_sync_service_to_server(self.server, store)
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def test_get_events_over_grpc(self):
        """Should be able to call GetEvents over a real gRPC connection."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=0,
            max_count=10,
        )
        # Use a generic unary-unary call
        response = self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )(request)
        self.assertIsInstance(response, sync_pb2.GetEventsResponse)
        self.assertGreater(len(response.events), 0)

    def test_get_events_unknown_method_fails(self):
        """Calling an unknown method should fail with UNIMPLEMENTED."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self.channel.unary_unary(
                "/vanpilot.v1.SyncService/NonExistent",
                request_serializer=lambda x: b"",
                response_deserializer=lambda x: x,
            )(b"")
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.UNIMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
