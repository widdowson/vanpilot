"""Unit tests for the smoke test runner.

Tests the supervisor pipeline (MCP → events → gRPC) without requiring
an instance manager or emulator. Uses in-process gRPC only.
"""

import base64
import unittest
from concurrent import futures

import grpc

from proto.vanpilot.v1 import sync_pb2

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore, McpBridge
from supervisor.src.sync_service import add_sync_service_to_server

import mcp.src.handlers as handlers
from mcp.src.handlers import (
    handle_submit_bitmap,
    handle_display_bitmap,
    set_event_callback,
)
from mcp.src.png_util import make_png


class SupervisorPipelineTest(unittest.TestCase):
    """Test the MCP → supervisor → gRPC event pipeline."""

    def setUp(self):
        handlers.reset()
        self.event_store = EventStore()
        self.bitmap_store = BitmapStore()
        self.bridge = McpBridge(self.event_store, self.bitmap_store)

        def on_mcp_event(event_type, cache_key, image_data):
            if event_type == "bitmap_submitted":
                self.bridge.on_bitmap_submitted(cache_key, image_data)
            elif event_type == "display_requested":
                self.bridge.on_display_requested(cache_key)

        set_event_callback(on_mcp_event)

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        add_sync_service_to_server(
            self.server, self.event_store, self.bitmap_store
        )
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")

    def tearDown(self):
        handlers.reset()
        self.channel.close()
        self.server.stop(grace=0)

    def _get_events(self, since_ms=0):
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=since_ms, max_count=100,
        )
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )(request)

    def _get_bitmap(self, cache_key):
        request = sync_pb2.GetBitmapRequest(cache_key=cache_key)
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetBitmap",
            request_serializer=sync_pb2.GetBitmapRequest.SerializeToString,
            response_deserializer=sync_pb2.GetBitmapResponse.FromString,
        )(request)

    def test_submit_and_display_creates_both_events(self):
        """Full MCP flow creates both bitmap_payload and display_command."""
        png_data = make_png(100, 100, (255, 0, 0))
        b64 = base64.b64encode(png_data).decode()

        result = handle_submit_bitmap(image_data=b64)
        cache_key = result["cache_key"]
        handle_display_bitmap(cache_key=cache_key)

        response = self._get_events()
        payload_types = [e.WhichOneof("payload") for e in response.events]
        self.assertIn("bitmap_payload", payload_types)
        self.assertIn("display_command", payload_types)

    def test_display_command_has_correct_cache_key(self):
        """DisplayCommand event contains the submitted bitmap's cache key."""
        png_data = make_png(50, 50, (0, 255, 0))
        b64 = base64.b64encode(png_data).decode()

        result = handle_submit_bitmap(image_data=b64)
        cache_key = result["cache_key"]
        handle_display_bitmap(cache_key=cache_key)

        response = self._get_events()
        display_events = [
            e for e in response.events
            if e.WhichOneof("payload") == "display_command"
        ]
        self.assertEqual(len(display_events), 1)
        self.assertEqual(display_events[0].display_command.cache_key, cache_key)

    def test_bitmap_retrievable_via_get_bitmap(self):
        """Submitted bitmap is retrievable via GetBitmap RPC."""
        png_data = make_png(10, 10, (0, 0, 255))
        b64 = base64.b64encode(png_data).decode()

        result = handle_submit_bitmap(image_data=b64)
        cache_key = result["cache_key"]

        resp = self._get_bitmap(cache_key)
        self.assertTrue(resp.HasField("bitmap"))
        self.assertEqual(resp.bitmap.image_data, png_data)

    def test_unknown_bitmap_returns_empty(self):
        """GetBitmap for unknown key returns empty response."""
        resp = self._get_bitmap("0xNONEXISTENT")
        self.assertFalse(resp.HasField("bitmap"))


class TestBitmapGenerationTest(unittest.TestCase):
    """Test that make_png generates valid test bitmaps."""

    def test_generates_valid_png(self):
        png = make_png(100, 100, (255, 0, 0))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(png), 100)

    def test_different_colors_produce_different_keys(self):
        from mcp.src.png_util import png_cache_key
        png1 = make_png(10, 10, (255, 0, 0))
        png2 = make_png(10, 10, (0, 255, 0))
        self.assertNotEqual(png_cache_key(png1), png_cache_key(png2))


if __name__ == "__main__":
    unittest.main()
