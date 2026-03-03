"""Tests for the gRPC server lifecycle."""

import unittest
import grpc

from supervisor.src.android_app_client import AndroidAppClient
from supervisor.src.server import create_server, create_android_app_client
from supervisor.src.mcp_bridge import McpBridge
from proto.vanpilot.v1 import sync_pb2


class ServerTest(unittest.TestCase):

    def test_create_server_returns_server_and_bridge(self):
        """create_server should return a gRPC server instance."""
        server, port, bridge, _tailer = create_server(port=0)
        self.assertIsNotNone(server)
        self.assertGreater(port, 0)
        self.assertIsInstance(bridge, McpBridge)
        server.stop(grace=0)

    def test_server_responds_to_get_events(self):
        """A created server should handle GetEvents calls."""
        server, port, _bridge, _tailer = create_server(port=0)
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
        """When port=0, the server should bind to a random free port."""
        server, port, _bridge, _tailer = create_server(port=0)
        self.assertGreater(port, 0)
        server.stop(grace=0)


class CreateAndroidAppClientTest(unittest.TestCase):

    def test_returns_client_and_channel(self):
        """create_android_app_client returns an AndroidAppClient and channel."""
        client, channel = create_android_app_client("localhost:9999")
        self.assertIsInstance(client, AndroidAppClient)
        self.assertIsNotNone(channel)
        channel.close()

    def test_default_target(self):
        """create_android_app_client with no args uses localhost:50052."""
        client, channel = create_android_app_client()
        self.assertIsInstance(client, AndroidAppClient)
        channel.close()


if __name__ == "__main__":
    unittest.main()
