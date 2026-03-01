"""End-to-end integration test for the gRPC pipeline.

Tests the full flow: MCP submit_bitmap/display_bitmap -> supervisor events ->
gRPC GetEvents/GetBitmap -> client receives correct data.

This is the Phase 7 integration test that verifies the wiring between
the MCP server, supervisor, and gRPC client.
"""

import base64
import hashlib
import struct
import unittest
import zlib
import grpc
from concurrent import futures

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore, McpBridge
from supervisor.src.sync_service import add_sync_service_to_server
from mcp.src.handlers import (
    handle_submit_bitmap,
    handle_display_bitmap,
    set_event_callback,
)
import mcp.src.handlers as handlers
from proto.vanpilot.v1 import sync_pb2


def _make_test_png(r: int, g: int, b: int) -> bytes:
    """Generate a minimal 1x1 PNG with a specific RGB color for testing."""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_data = bytes([0, r, g, b])
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


class EndToEndGrpcTest(unittest.TestCase):
    """Full pipeline test: MCP -> supervisor -> gRPC client."""

    def setUp(self):
        handlers.reset()
        self.event_store = EventStore()
        self.bitmap_store = BitmapStore()
        self.bridge = McpBridge(self.event_store, self.bitmap_store)

        # Wire MCP callbacks to the bridge
        def on_mcp_event(event_type, cache_key, image_data):
            if event_type == "bitmap_submitted":
                self.bridge.on_bitmap_submitted(cache_key, image_data)
            elif event_type == "display_requested":
                self.bridge.on_display_requested(cache_key)

        set_event_callback(on_mcp_event)

        # Start gRPC server
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

    def _get_events(self, since_ms=0, max_count=100):
        """Helper: call GetEvents over gRPC."""
        request = sync_pb2.GetEventsRequest(
            since_timestamp_ms=since_ms,
            max_count=max_count,
        )
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetEvents",
            request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
            response_deserializer=sync_pb2.GetEventsResponse.FromString,
        )(request)

    def _get_bitmap(self, cache_key):
        """Helper: call GetBitmap over gRPC."""
        request = sync_pb2.GetBitmapRequest(cache_key=cache_key)
        return self.channel.unary_unary(
            "/vanpilot.v1.SyncService/GetBitmap",
            request_serializer=sync_pb2.GetBitmapRequest.SerializeToString,
            response_deserializer=sync_pb2.GetBitmapResponse.FromString,
        )(request)

    def test_submit_bitmap_creates_event(self):
        """submit_bitmap via MCP should create a BitmapPayload event."""
        png_data = _make_test_png(255, 0, 0)
        image_b64 = base64.b64encode(png_data).decode()
        result = handle_submit_bitmap(image_data=image_b64)
        cache_key = result["cache_key"]

        response = self._get_events()
        bitmap_events = [
            e for e in response.events
            if e.WhichOneof("payload") == "bitmap_payload"
        ]
        self.assertEqual(len(bitmap_events), 1)
        self.assertEqual(bitmap_events[0].bitmap_payload.cache_key, cache_key)
        self.assertEqual(bitmap_events[0].bitmap_payload.image_data, png_data)

    def test_display_bitmap_creates_event(self):
        """display_bitmap via MCP should create a DisplayCommand event."""
        png_data = _make_test_png(0, 255, 0)
        image_b64 = base64.b64encode(png_data).decode()
        result = handle_submit_bitmap(image_data=image_b64)
        cache_key = result["cache_key"]

        handle_display_bitmap(cache_key=cache_key)

        response = self._get_events()
        display_events = [
            e for e in response.events
            if e.WhichOneof("payload") == "display_command"
        ]
        self.assertEqual(len(display_events), 1)
        self.assertEqual(display_events[0].display_command.cache_key, cache_key)

    def test_get_bitmap_returns_submitted_image(self):
        """GetBitmap should return the PNG data submitted via MCP."""
        png_data = _make_test_png(0, 0, 255)
        image_b64 = base64.b64encode(png_data).decode()
        result = handle_submit_bitmap(image_data=image_b64)
        cache_key = result["cache_key"]

        response = self._get_bitmap(cache_key)
        self.assertTrue(response.HasField("bitmap"))
        self.assertEqual(response.bitmap.cache_key, cache_key)
        self.assertEqual(response.bitmap.image_data, png_data)

    def test_get_bitmap_unknown_key_returns_empty(self):
        """GetBitmap for an unknown key should return empty response."""
        response = self._get_bitmap("0xDEADBEEF")
        self.assertFalse(response.HasField("bitmap"))

    def test_full_flow_submit_display_get_events_get_bitmap(self):
        """Full pipeline: submit -> display -> GetEvents -> GetBitmap."""
        # Step 1: Submit a bitmap via MCP
        png_data = _make_test_png(128, 64, 32)
        image_b64 = base64.b64encode(png_data).decode()
        submit_result = handle_submit_bitmap(image_data=image_b64)
        cache_key = submit_result["cache_key"]

        # Step 2: Display it via MCP
        display_result = handle_display_bitmap(cache_key=cache_key)
        self.assertTrue(display_result["success"])

        # Step 3: Pull events via gRPC (as Android app would)
        response = self._get_events()
        payload_types = [e.WhichOneof("payload") for e in response.events]
        self.assertIn("bitmap_payload", payload_types)
        self.assertIn("display_command", payload_types)

        # Step 4: Retrieve the bitmap via gRPC (as Android app would)
        bitmap_resp = self._get_bitmap(cache_key)
        self.assertTrue(bitmap_resp.HasField("bitmap"))
        self.assertEqual(bitmap_resp.bitmap.image_data, png_data)

    def test_events_ordered_by_timestamp(self):
        """Events from the pipeline should be in timestamp order."""
        for i in range(3):
            data = _make_test_png(i * 80, 0, 0)
            handle_submit_bitmap(image_data=base64.b64encode(data).decode())

        response = self._get_events()
        timestamps = [e.timestamp_ms for e in response.events]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_timestamp_filtering_works_with_bridge_events(self):
        """since_timestamp_ms should correctly filter bridge-created events."""
        data1 = _make_test_png(255, 0, 0)
        handle_submit_bitmap(image_data=base64.b64encode(data1).decode())

        # Get all events and find the bitmap event's timestamp
        all_events = self._get_events()
        bitmap_events = [
            e for e in all_events.events
            if e.WhichOneof("payload") == "bitmap_payload"
        ]
        self.assertGreater(len(bitmap_events), 0)
        bitmap_ts = bitmap_events[0].timestamp_ms

        # Query with timestamp after the bitmap event
        later = self._get_events(since_ms=bitmap_ts + 1)
        later_bitmap_events = [
            e for e in later.events
            if e.WhichOneof("payload") == "bitmap_payload"
        ]
        self.assertEqual(len(later_bitmap_events), 0)


if __name__ == "__main__":
    unittest.main()
