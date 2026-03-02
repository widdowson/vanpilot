"""gRPC client for the Android app's AndroidAppService.

The supervisor uses this to call RPCs on the Android app (reverse direction).
This enables features like querying the current display state, requesting
screenshots, and checking bitmap cache contents.
"""

from __future__ import annotations

from typing import List, Optional

import grpc

from proto.vanpilot.v1 import screenshot_pb2


class AndroidAppClient:
    """Client for calling RPCs on the Android app's reverse gRPC server.

    The Android app hosts an AndroidAppService gRPC server (typically on
    port 50052). The supervisor connects to it via this client.
    """

    def __init__(self, channel: grpc.Channel) -> None:
        self._get_current_display = channel.unary_unary(
            "/vanpilot.v1.AndroidAppService/GetCurrentDisplay",
            request_serializer=screenshot_pb2.GetCurrentDisplayRequest.SerializeToString,
            response_deserializer=screenshot_pb2.GetCurrentDisplayResponse.FromString,
        )
        self._request_screenshot = channel.unary_unary(
            "/vanpilot.v1.AndroidAppService/RequestScreenshot",
            request_serializer=screenshot_pb2.RequestScreenshotRequest.SerializeToString,
            response_deserializer=screenshot_pb2.RequestScreenshotResponse.FromString,
        )
        self._query_cache = channel.unary_unary(
            "/vanpilot.v1.AndroidAppService/QueryCache",
            request_serializer=screenshot_pb2.QueryCacheRequest.SerializeToString,
            response_deserializer=screenshot_pb2.QueryCacheResponse.FromString,
        )

    def get_current_display(self) -> str:
        """Get the cache key currently displayed on the Android app.

        Returns an empty string if nothing is displayed.
        """
        request = screenshot_pb2.GetCurrentDisplayRequest()
        response = self._get_current_display(request)
        return response.current_cache_key

    def request_screenshot(self) -> bytes:
        """Request a PNG screenshot from the Android app."""
        request = screenshot_pb2.RequestScreenshotRequest()
        response = self._request_screenshot(request)
        return response.screenshot

    def query_cache(
        self, keys: Optional[List[str]] = None
    ) -> tuple[list[str], list[str]]:
        """Check which cache keys the app holds.

        Args:
            keys: Specific keys to check. If None/empty, returns all known keys.

        Returns:
            A tuple of (present_keys, missing_keys).
        """
        request = screenshot_pb2.QueryCacheRequest(keys=keys or [])
        response = self._query_cache(request)
        return list(response.present_keys), list(response.missing_keys)
