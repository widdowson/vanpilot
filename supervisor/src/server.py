"""gRPC server setup and entry point for the supervisor."""

from __future__ import annotations

import os
from concurrent import futures
from typing import Optional

import grpc

from supervisor.src.android_app_client import AndroidAppClient
from supervisor.src.event_store import EventStore
from supervisor.src.log_tailer import LogTailer
from supervisor.src.mcp_bridge import BitmapStore, McpBridge
from supervisor.src.sync_service import add_sync_service_to_server

_DEFAULT_HOST = "[::]"
_DEFAULT_PORT = 50051
_DEFAULT_APP_PORT = 50052
_DEFAULT_LOG_DIR = os.path.expanduser("~/.claude/projects")
_MAX_WORKERS = 4


def parse_server_config() -> tuple:
    """Parse server configuration from environment variables.

    Environment variables:
        GRPC_HOST: Bind address for the gRPC server (default: [::]).
        GRPC_PORT: Listen port for the gRPC server (default: 50051).
        GRPC_APP_TARGET: Android app reverse-service address (default: localhost:50052).

    Returns:
        A tuple of (host, port, app_target).

    Raises:
        ValueError: If GRPC_PORT is not a valid integer.
    """
    host = os.environ.get("GRPC_HOST", _DEFAULT_HOST)
    port = int(os.environ.get("GRPC_PORT", str(_DEFAULT_PORT)))
    app_target = os.environ.get(
        "GRPC_APP_TARGET", f"localhost:{_DEFAULT_APP_PORT}"
    )
    return host, port, app_target


def create_server(
    port: int = _DEFAULT_PORT,
    host: str = _DEFAULT_HOST,
    app_client: Optional[AndroidAppClient] = None,
) -> tuple:
    """Create and configure the supervisor gRPC server.

    Args:
        port: The port to bind to. Use 0 for a random free port.
        host: The bind address (default: [::] for all interfaces).
        app_client: Optional AndroidAppClient for reverse-path calls.
            When provided, enables blocking=true for display_bitmap (AC-6.3).

    Returns:
        A tuple of (grpc.Server, actual_port, McpBridge, LogTailer).
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
    store = EventStore()
    bitmap_store = BitmapStore()
    bridge = McpBridge(store, bitmap_store, app_client=app_client)
    add_sync_service_to_server(server, store, bitmap_store)
    log_dir = os.environ.get("AGENT_LOG_DIR", _DEFAULT_LOG_DIR)
    tailer = LogTailer(store, log_dir=log_dir)
    actual_port = server.add_insecure_port(f"{host}:{port}")
    return server, actual_port, bridge, tailer


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
