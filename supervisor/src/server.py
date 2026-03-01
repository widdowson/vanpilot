"""gRPC server setup and entry point for the supervisor."""

from concurrent import futures

import grpc

from supervisor.src.event_store import EventStore
from supervisor.src.sync_service import add_sync_service_to_server

_DEFAULT_PORT = 50051
_MAX_WORKERS = 4


def create_server(port: int = _DEFAULT_PORT) -> tuple:
    """Create and configure the supervisor gRPC server.

    Args:
        port: Port to listen on. Use 0 for a random free port.

    Returns:
        A tuple of (grpc.Server, actual_port).
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
    store = EventStore()
    add_sync_service_to_server(server, store)
    actual_port = server.add_insecure_port(f"[::]:{port}")
    return server, actual_port
