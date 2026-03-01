"""gRPC SyncService implementation using manual method handlers."""

from __future__ import annotations

from typing import Optional

import grpc

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector
from supervisor.src.mcp_bridge import BitmapStore


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
        data = self._bitmap_store.get(request.cache_key)
        if data is None:
            return sync_pb2.GetBitmapResponse()
        return sync_pb2.GetBitmapResponse(
            bitmap=sync_pb2.BitmapPayload(
                cache_key=request.cache_key,
                image_data=data,
            ),
        )


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
        }

    def service(self, handler_call_details):
        return self._method_handlers.get(handler_call_details.method)
