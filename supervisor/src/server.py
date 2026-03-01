"""gRPC server setup and entry point for the supervisor."""

from concurrent import futures

import grpc

from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore, McpBridge
from supervisor.src.sync_service import add_sync_service_to_server

_DEFAULT_PORT = 50051
_MAX_WORKERS = 4


def create_server(port: int = _DEFAULT_PORT) -> tuple:
    """Create and configure the supervisor gRPC server.

    Returns:
        A tuple of (grpc.Server, actual_port, McpBridge).
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
    store = EventStore()
    bitmap_store = BitmapStore()
    bridge = McpBridge(store, bitmap_store)
    add_sync_service_to_server(server, store, bitmap_store)
    actual_port = server.add_insecure_port(f"[::]:{port}")
    return server, actual_port, bridge
