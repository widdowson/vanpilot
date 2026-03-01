"""gRPC SyncService implementation using manual method handlers."""

import grpc

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore
from supervisor.src.mcp_bridge import BitmapStore


class SyncServiceServicer:
    """Implements the SyncService RPCs."""

    def __init__(self, store: EventStore, bitmap_store: BitmapStore | None = None) -> None:
        self._store = store
        self._bitmap_store = bitmap_store or BitmapStore()

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
    server: grpc.Server, store: EventStore, bitmap_store: BitmapStore | None = None,
) -> None:
    """Register SyncService handlers on a gRPC server."""
    servicer = SyncServiceServicer(store, bitmap_store)
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
