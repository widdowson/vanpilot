"""gRPC server setup and entry point for the supervisor."""

from __future__ import annotations

from concurrent import futures
from typing import Optional

import grpc

from supervisor.src.android_app_client import AndroidAppClient
from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore, McpBridge
from supervisor.src.sync_service import add_sync_service_to_server

_DEFAULT_PORT = 50051
_DEFAULT_APP_PORT = 50052
_MAX_WORKERS = 4


def create_server(
    port: int = _DEFAULT_PORT,
    app_client: Optional[AndroidAppClient] = None,
) -> tuple:
    """Create and configure the supervisor gRPC server.

    Args:
        port: Port to listen on.
        app_client: Optional AndroidAppClient for reverse-path calls.
            When provided, enables blocking=true for display_bitmap (AC-6.3).

    Returns:
        A tuple of (grpc.Server, actual_port, McpBridge).
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
    store = EventStore()
    bitmap_store = BitmapStore()
    bridge = McpBridge(store, bitmap_store, app_client=app_client)
    add_sync_service_to_server(server, store, bitmap_store)
    actual_port = server.add_insecure_port(f"[::]:{port}")
    return server, actual_port, bridge


def create_android_app_client(
    target: Optional[str] = None,
) -> tuple[AndroidAppClient, grpc.Channel]:
    """Create a gRPC client for calling the Android app's reverse service.

    Args:
        target: The Android app's gRPC address (e.g., "pixel.tailnet:50052").
            Defaults to localhost:50052 for local development.

    Returns:
        A tuple of (AndroidAppClient, grpc.Channel). Caller must close the
        channel when done.
    """
    if target is None:
        target = f"localhost:{_DEFAULT_APP_PORT}"
    channel = grpc.insecure_channel(target)
    client = AndroidAppClient(channel)
    return client, channel
