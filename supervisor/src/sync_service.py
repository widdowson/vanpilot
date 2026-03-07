"""gRPC SyncService implementation using manual method handlers."""

from __future__ import annotations

import time
from typing import Optional

import grpc

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector
from supervisor.src.mcp_bridge import BitmapStore

# Fallback client ID when context is None (unit tests).
_FALLBACK_CLIENT_ID = "default"


class SyncServiceServicer:
    """Implements the SyncService RPCs."""

    def __init__(
        self,
        store: EventStore,
        bitmap_store: BitmapStore | None = None,
        input_injector: Optional[InputInjector] = None,
    ) -> None:
        self._store = store
        self._bitmap_store = bitmap_store or BitmapStore()
        self._input_injector = input_injector

    @staticmethod
    def _client_id(context: grpc.ServicerContext | None) -> str:
        """Derive a client identifier from the gRPC peer address."""
        if context is None:
            return _FALLBACK_CLIENT_ID
        try:
            peer = context.peer()
            if peer:
                return peer
        except Exception:
            pass
        return _FALLBACK_CLIENT_ID

    def GetEvents(
        self,
        request: sync_pb2.GetEventsRequest,
        context: grpc.ServicerContext,
    ) -> sync_pb2.GetEventsResponse:
        events = self._store.get_events(
            since_timestamp_ms=request.since_timestamp_ms,
            max_count=request.max_count,
        )
        return sync_pb2.GetEventsResponse(events=events)

    def SendUserInput(
        self,
        request: sync_pb2.SendUserInputRequest,
        context: grpc.ServicerContext,
    ) -> sync_pb2.SendUserInputResponse:
        if self._input_injector is None:
            return sync_pb2.SendUserInputResponse(accepted=False)
        target = request.target_agent_id or "lead"
        session_name = f"vanpilot-{target}"
        self._input_injector.inject_async(session_name, request.text, target)
        return sync_pb2.SendUserInputResponse(accepted=True)

    def GetBitmap(
        self,
        request: sync_pb2.GetBitmapRequest,
        context: grpc.ServicerContext,
    ) -> sync_pb2.GetBitmapResponse:
        client_id = self._client_id(context)
        wait_ms = request.wait_ms
        deadline = time.monotonic() + wait_ms / 1000.0 if wait_ms > 0 else 0

        while True:
            data = self._bitmap_store.get(request.cache_key)
            if data is not None:
                self._bitmap_store.mark_sent(client_id, request.cache_key)
                return sync_pb2.GetBitmapResponse(
                    bitmap=sync_pb2.BitmapPayload(
                        cache_key=request.cache_key,
                        image_data=data,
                    ),
                )
            if wait_ms <= 0 or time.monotonic() >= deadline:
                return sync_pb2.GetBitmapResponse()
            # Exit cleanly if the client disconnects mid-poll.
            if context is not None and not context.is_active():
                return sync_pb2.GetBitmapResponse()
            # Block on event instead of busy-polling — doesn't hold CPU
            # and wakes immediately when a new bitmap is stored.
            remaining = deadline - time.monotonic()
            if remaining > 0:
                self._bitmap_store.wait_for_new_bitmap(timeout=remaining)

    def ReconcileCache(
        self,
        request: sync_pb2.ReconcileCacheRequest,
        context: grpc.ServicerContext,
    ) -> sync_pb2.ReconcileCacheResponse:
        client_id = self._client_id(context)
        missing = self._bitmap_store.reconcile(
            client_id, set(request.present_keys)
        )
        return sync_pb2.ReconcileCacheResponse(missing_keys=list(missing))


def add_sync_service_to_server(
    server: grpc.Server,
    store: EventStore,
    bitmap_store: BitmapStore | None = None,
    input_injector: Optional[InputInjector] = None,
) -> None:
    """Register SyncService handlers on a gRPC server.

    Uses manual method handlers since we don't have generated _pb2_grpc stubs.
    """
    servicer = SyncServiceServicer(store, bitmap_store, input_injector)

    handler = _SyncServiceGenericHandler(servicer)
    server.add_generic_rpc_handlers([handler])


class _SyncServiceGenericHandler(grpc.GenericRpcHandler):
    """Maps SyncService method paths to handler functions."""

    def __init__(self, servicer: SyncServiceServicer) -> None:
        self._method_handlers = {
            "/vanpilot.v1.SyncService/GetEvents": grpc.unary_unary_rpc_method_handler(
                servicer.GetEvents,
                request_deserializer=sync_pb2.GetEventsRequest.FromString,
                response_serializer=sync_pb2.GetEventsResponse.SerializeToString,
            ),
            "/vanpilot.v1.SyncService/SendUserInput": grpc.unary_unary_rpc_method_handler(
                servicer.SendUserInput,
                request_deserializer=sync_pb2.SendUserInputRequest.FromString,
                response_serializer=sync_pb2.SendUserInputResponse.SerializeToString,
            ),
            "/vanpilot.v1.SyncService/GetBitmap": grpc.unary_unary_rpc_method_handler(
                servicer.GetBitmap,
                request_deserializer=sync_pb2.GetBitmapRequest.FromString,
                response_serializer=sync_pb2.GetBitmapResponse.SerializeToString,
            ),
            "/vanpilot.v1.SyncService/ReconcileCache": grpc.unary_unary_rpc_method_handler(
                servicer.ReconcileCache,
                request_deserializer=sync_pb2.ReconcileCacheRequest.FromString,
                response_serializer=sync_pb2.ReconcileCacheResponse.SerializeToString,
            ),
        }

    def service(self, handler_call_details):
        return self._method_handlers.get(handler_call_details.method)
