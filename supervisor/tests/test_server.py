"""Tests for the gRPC server lifecycle."""

import unittest
import grpc

from supervisor.src.server import create_server
from supervisor.src.mcp_bridge import McpBridge
from proto.vanpilot.v1 import sync_pb2


class ServerTest(unittest.TestCase):

    def test_create_server_returns_server_and_bridge(self):
        server, port, bridge = create_server(port=0)
        self.assertIsNotNone(server)
        self.assertGreater(port, 0)
        self.assertIsInstance(bridge, McpBridge)
        server.stop(grace=0)

    def test_server_responds_to_get_events(self):
        server, port, _bridge = create_server(port=0)
        server.start()
        try:
            channel = grpc.insecure_channel(f"localhost:{port}")
            response = channel.unary_unary(
                "/vanpilot.v1.SyncService/GetEvents",
                request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
                response_deserializer=sync_pb2.GetEventsResponse.FromString,
            )(sync_pb2.GetEventsRequest(since_timestamp_ms=0, max_count=5))
            self.assertIsInstance(response, sync_pb2.GetEventsResponse)
            channel.close()
        finally:
            server.stop(grace=0)

    def test_server_uses_specified_port(self):
        server, port, _bridge = create_server(port=0)
        self.assertGreater(port, 0)
        server.stop(grace=0)


if __name__ == "__main__":
    unittest.main()
