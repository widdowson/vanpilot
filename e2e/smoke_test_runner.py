"""Full-stack E2E smoke test runner.

Orchestrates: instance manager → emulator+DHU → supervisor → MCP → display.

Verifies that a bitmap submitted via MCP ends up rendered on the Android
Auto head unit display by:
1. Creating an emulator+DHU instance via the instance manager
2. Starting a supervisor gRPC server (in-process) with MCP bridge wiring
3. Submitting a test bitmap via MCP handlers
4. Issuing a display_bitmap command via MCP handlers
5. Polling the supervisor's GetEvents (as the Android app would)
6. Verifying the display_command event contains the expected cache key
7. Capturing a DHU screenshot via the instance manager
8. (Optional) Comparing the screenshot against a golden

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to the VanPilot APK (optional)
"""

import base64
import os
import time
from concurrent import futures
from typing import Optional

import grpc

from proto.vanpilot.v1 import sync_pb2
from proto.vanpilot.v1 import instance_manager_pb2

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

from goldens.golden_test_harness import InstanceManagerClient


INSTANCE_MANAGER_ADDR = os.environ.get("INSTANCE_MANAGER_ADDR", "localhost:50061")
VANPILOT_APK = os.environ.get("VANPILOT_APK", "")

# Default test bitmap: a 100x100 red square
DEFAULT_TEST_COLOR = (255, 0, 0)
DEFAULT_TEST_SIZE = (100, 100)


class SmokeTestRunner:
    """Orchestrates the full-stack E2E smoke test."""

    def __init__(
        self,
        instance_manager_addr: str = INSTANCE_MANAGER_ADDR,
        instance_name: str = "smoke-test",
        test_color: tuple = DEFAULT_TEST_COLOR,
        test_size: tuple = DEFAULT_TEST_SIZE,
    ):
        self.instance_manager_addr = instance_manager_addr
        self.instance_name = instance_name
        self.test_color = test_color
        self.test_size = test_size

        # Components (initialized in setup)
        self._im_client: Optional[InstanceManagerClient] = None
        self._instance_info = None
        self._event_store: Optional[EventStore] = None
        self._bitmap_store: Optional[BitmapStore] = None
        self._bridge: Optional[McpBridge] = None
        self._grpc_server = None
        self._supervisor_port: Optional[int] = None

    def setup(self) -> None:
        """Set up all components: instance manager, supervisor, MCP wiring."""
        # 1. Create emulator+DHU instance
        self._im_client = InstanceManagerClient(self.instance_manager_addr)
        resp = self._im_client.create_instance(name=self.instance_name)
        self._instance_info = resp.instance

        # 2. Set up supervisor in-process
        handlers.reset()
        self._event_store = EventStore()
        self._bitmap_store = BitmapStore()
        self._bridge = McpBridge(self._event_store, self._bitmap_store)

        # 3. Wire MCP callbacks to bridge
        def on_mcp_event(event_type, cache_key, image_data):
            if event_type == "bitmap_submitted":
                self._bridge.on_bitmap_submitted(cache_key, image_data)
            elif event_type == "display_requested":
                self._bridge.on_display_requested(cache_key)

        set_event_callback(on_mcp_event)

        # 4. Start gRPC server
        self._grpc_server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=2)
        )
        add_sync_service_to_server(
            self._grpc_server, self._event_store, self._bitmap_store
        )
        self._supervisor_port = self._grpc_server.add_insecure_port("[::]:0")
        self._grpc_server.start()

        # 5. Install APK if configured
        if VANPILOT_APK:
            from goldens.golden_test_harness import install_apk, launch_vanpilot_app
            install_apk(self._instance_info.adb_port, VANPILOT_APK)
            launch_vanpilot_app(self._instance_info.adb_port)
            time.sleep(10)  # Wait for app to render

    def teardown(self) -> None:
        """Clean up all components."""
        handlers.reset()
        if self._grpc_server:
            self._grpc_server.stop(grace=0)
        if self._im_client:
            try:
                self._im_client.destroy_instance(self.instance_name)
            except grpc.RpcError:
                pass
            self._im_client.close()

    @property
    def supervisor_port(self) -> int:
        return self._supervisor_port

    @property
    def instance_info(self):
        return self._instance_info

    def submit_and_display_test_bitmap(self) -> str:
        """Submit a test bitmap via MCP and display it.

        Returns the cache key of the submitted bitmap.
        """
        w, h = self.test_size
        png_data = make_png(w, h, self.test_color)
        image_b64 = base64.b64encode(png_data).decode()

        result = handle_submit_bitmap(image_data=image_b64)
        cache_key = result["cache_key"]

        display_result = handle_display_bitmap(cache_key=cache_key)
        if not display_result.get("success"):
            raise RuntimeError(
                f"display_bitmap failed: {display_result.get('error')}"
            )

        return cache_key

    def get_events(self, since_ms: int = 0) -> list:
        """Poll supervisor events via gRPC (as Android app would)."""
        channel = grpc.insecure_channel(
            f"localhost:{self._supervisor_port}"
        )
        try:
            request = sync_pb2.GetEventsRequest(
                since_timestamp_ms=since_ms,
                max_count=100,
            )
            response = channel.unary_unary(
                "/vanpilot.v1.SyncService/GetEvents",
                request_serializer=sync_pb2.GetEventsRequest.SerializeToString,
                response_deserializer=sync_pb2.GetEventsResponse.FromString,
            )(request)
            return list(response.events)
        finally:
            channel.close()

    def verify_display_command_in_events(
        self, cache_key: str, since_ms: int = 0,
    ) -> bool:
        """Check that a DisplayCommand with the given cache_key exists."""
        events = self.get_events(since_ms=since_ms)
        for event in events:
            if event.WhichOneof("payload") == "display_command":
                if event.display_command.cache_key == cache_key:
                    return True
        return False

    def verify_bitmap_retrievable(self, cache_key: str) -> bool:
        """Check that GetBitmap returns data for the given cache_key."""
        channel = grpc.insecure_channel(
            f"localhost:{self._supervisor_port}"
        )
        try:
            request = sync_pb2.GetBitmapRequest(cache_key=cache_key)
            response = channel.unary_unary(
                "/vanpilot.v1.SyncService/GetBitmap",
                request_serializer=sync_pb2.GetBitmapRequest.SerializeToString,
                response_deserializer=sync_pb2.GetBitmapResponse.FromString,
            )(request)
            return response.HasField("bitmap")
        finally:
            channel.close()

    def capture_dhu_screenshot(self) -> bytes:
        """Capture DHU screenshot via the instance manager."""
        resp = self._im_client.screenshot_instance(self.instance_name)
        return resp.dhu_screenshot_png
