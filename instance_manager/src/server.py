"""gRPC + HTTP server setup and entry point for the instance manager."""

from __future__ import annotations

import signal
import sys
import threading
import time
from concurrent import futures

import grpc

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle, SubprocessRunner
from instance_manager.src.instance_manager_service import (
    add_instance_manager_service_to_server,
)
from instance_manager.src.instance_store import InstanceStore
from instance_manager.src.port_allocator import PortAllocator
from instance_manager.src.web_server import start_web_server

_MAX_WORKERS = 4


def _screenshot_refresh_loop(
    store: InstanceStore,
    lifecycle: EmulatorLifecycle,
    interval: int = 30,
) -> None:
    """Background loop to refresh screenshots of running instances."""
    while True:
        time.sleep(interval)
        for record in store.get_running():
            try:
                png = lifecycle.screenshot(record)
                store.update(
                    record.name,
                    last_screenshot_png=png,
                    last_screenshot_at_ms=int(time.time() * 1000),
                )
            except Exception:
                pass  # Don't crash the refresh loop


def create_server(
    grpc_port: int = 50061,
    http_port: int = 8080,
    max_slots: int = 8,
    runner: SubprocessRunner | None = None,
) -> tuple[grpc.Server, threading.Thread, InstanceStore]:
    """Create and configure the instance manager servers.

    Returns:
        (grpc_server, http_thread, instance_store)
    """
    store = InstanceStore()
    port_allocator = PortAllocator(max_slots=max_slots)
    subprocess_runner = runner or SubprocessRunner()
    lifecycle = EmulatorLifecycle(store, subprocess_runner)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
    add_instance_manager_service_to_server(
        server, store, lifecycle, port_allocator
    )
    actual_port = server.add_insecure_port(f"[::]:{grpc_port}")

    _, http_thread = start_web_server(store, http_port)

    # Background screenshot refresh daemon
    refresh_thread = threading.Thread(
        target=_screenshot_refresh_loop,
        args=(store, lifecycle),
        daemon=True,
    )
    refresh_thread.start()

    return server, http_thread, store


def main():
    """Entry point: start the instance manager service."""
    server, http_thread, store = create_server()
    server.start()
    print("Instance manager gRPC on :50061, HTTP dashboard on :8080", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: (server.stop(5), sys.exit(0)))
    server.wait_for_termination()


if __name__ == "__main__":
    main()
