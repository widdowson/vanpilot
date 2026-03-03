"""gRPC servicer for InstanceManagerService."""

from __future__ import annotations

import time

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle
from instance_manager.src.instance_store import (
    InstanceStore,
    InstanceRecord,
    RUNNING,
    DESTROYING,
)
from instance_manager.src.port_allocator import PortAllocator

_DEFAULT_AVD = "vanpilot_pixel9pro_api36"
_DEFAULT_SNAPSHOT = "aa_ready"


def _record_to_proto(record: InstanceRecord) -> instance_manager_pb2.InstanceInfo:
    """Convert an InstanceRecord to a proto InstanceInfo."""
    info = instance_manager_pb2.InstanceInfo(
        name=record.name,
        state=record.state,
        emulator_console_port=record.emulator_console_port,
        adb_port=record.adb_port,
        aa_forward_port=record.aa_forward_port,
        headful=record.headful,
        created_at_ms=record.created_at_ms,
        avd_name=record.avd_name,
    )
    if record.last_screenshot_png:
        info.last_screenshot_png = record.last_screenshot_png
    if record.last_emulator_screenshot_png:
        info.last_emulator_screenshot_png = record.last_emulator_screenshot_png
    return info


class InstanceManagerServicer:
    """Implements the InstanceManagerService RPCs."""

    def __init__(
        self,
        store: InstanceStore,
        lifecycle: EmulatorLifecycle,
        port_allocator: PortAllocator,
    ) -> None:
        self._store = store
        self._lifecycle = lifecycle
        self._port_allocator = port_allocator

    def CreateInstance(self, request, context):
        name = request.name
        if not name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")

        if self._store.get(name) is not None:
            context.abort(
                grpc.StatusCode.ALREADY_EXISTS,
                f"Instance '{name}' already exists",
            )

        avd_name = request.avd_name or _DEFAULT_AVD
        snapshot_name = request.snapshot_name or _DEFAULT_SNAPSHOT

        try:
            ports = self._port_allocator.allocate()
        except RuntimeError as e:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(e))

        self._store.create(
            name=name,
            emulator_console_port=ports.console_port,
            adb_port=ports.adb_port,
            aa_forward_port=ports.aa_forward_port,
            headful=request.headful,
            created_at_ms=int(time.time() * 1000),
            avd_name=avd_name,
        )

        try:
            record = self._lifecycle.create(
                name=name,
                avd_name=avd_name,
                snapshot_name=snapshot_name,
                headful=request.headful,
                ports=ports,
            )
            return instance_manager_pb2.CreateInstanceResponse(
                instance=_record_to_proto(record),
            )
        except Exception as e:
            self._port_allocator.release(ports.slot_index)
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def DestroyInstance(self, request, context):
        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )

        self._store.update(request.name, state=DESTROYING)

        try:
            self._lifecycle.destroy(record)
        except Exception:
            pass  # Best-effort cleanup

        # Find slot index from console port
        slot_index = (record.emulator_console_port - 5554) // 2
        try:
            self._port_allocator.release(slot_index)
        except ValueError:
            pass

        self._store.remove(request.name)
        return instance_manager_pb2.DestroyInstanceResponse()

    def ListInstances(self, request, context):
        records = self._store.list_all()
        return instance_manager_pb2.ListInstancesResponse(
            instances=[_record_to_proto(r) for r in records],
        )

    def GetInstance(self, request, context):
        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )
        return instance_manager_pb2.GetInstanceResponse(
            instance=_record_to_proto(record),
        )

    def ScreenshotInstance(self, request, context):
        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )
        if record.state != RUNNING:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Instance '{request.name}' is not running (state={record.state})",
            )

        try:
            serial = f"emulator-{record.emulator_console_port}"
            dhu_png = self._lifecycle.screenshot(record)
            emu_png = self._lifecycle.emulator_screenshot_to_bytes(serial)
            now_ms = int(time.time() * 1000)
            self._store.update(
                request.name,
                last_screenshot_png=dhu_png,
                last_emulator_screenshot_png=emu_png,
                last_screenshot_at_ms=now_ms,
            )
            return instance_manager_pb2.ScreenshotInstanceResponse(
                dhu_screenshot_png=dhu_png,
                emulator_screenshot_png=emu_png,
                captured_at_ms=now_ms,
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def RestartDhu(self, request, context):
        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )
        if record.state != RUNNING:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Instance '{request.name}' is not running (state={record.state})",
            )

        try:
            updated = self._lifecycle.restart_dhu(record)
            return instance_manager_pb2.RestartDhuResponse(
                instance=_record_to_proto(updated),
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def DhuCommand(self, request, context):
        if not request.command:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "command is required"
            )

        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )
        if record.state != RUNNING:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Instance '{request.name}' is not running (state={record.state})",
            )

        try:
            screenshot_png = self._lifecycle.dhu_command(
                record, request.command, request.capture_screenshot,
            )
            now_ms = int(time.time() * 1000)
            if screenshot_png:
                self._store.update(
                    request.name,
                    last_screenshot_png=screenshot_png,
                    last_screenshot_at_ms=now_ms,
                )
            return instance_manager_pb2.DhuCommandResponse(
                executed_at_ms=now_ms,
                screenshot_png=screenshot_png,
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))


def add_instance_manager_service_to_server(
    server: grpc.Server,
    store: InstanceStore,
    lifecycle: EmulatorLifecycle,
    port_allocator: PortAllocator,
) -> None:
    """Register the InstanceManagerService with a gRPC server."""
    servicer = InstanceManagerServicer(store, lifecycle, port_allocator)
    handler = _InstanceManagerGenericHandler(servicer)
    server.add_generic_rpc_handlers([handler])


class _InstanceManagerGenericHandler(grpc.GenericRpcHandler):
    """Maps InstanceManagerService method paths to handler functions."""

    _SERVICE = "vanpilot.v1.InstanceManagerService"

    def __init__(self, servicer: InstanceManagerServicer) -> None:
        self._method_handlers = {
            f"/{self._SERVICE}/CreateInstance":
                grpc.unary_unary_rpc_method_handler(
                    servicer.CreateInstance,
                    request_deserializer=instance_manager_pb2.CreateInstanceRequest.FromString,
                    response_serializer=instance_manager_pb2.CreateInstanceResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/DestroyInstance":
                grpc.unary_unary_rpc_method_handler(
                    servicer.DestroyInstance,
                    request_deserializer=instance_manager_pb2.DestroyInstanceRequest.FromString,
                    response_serializer=instance_manager_pb2.DestroyInstanceResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/ListInstances":
                grpc.unary_unary_rpc_method_handler(
                    servicer.ListInstances,
                    request_deserializer=instance_manager_pb2.ListInstancesRequest.FromString,
                    response_serializer=instance_manager_pb2.ListInstancesResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/GetInstance":
                grpc.unary_unary_rpc_method_handler(
                    servicer.GetInstance,
                    request_deserializer=instance_manager_pb2.GetInstanceRequest.FromString,
                    response_serializer=instance_manager_pb2.GetInstanceResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/ScreenshotInstance":
                grpc.unary_unary_rpc_method_handler(
                    servicer.ScreenshotInstance,
                    request_deserializer=instance_manager_pb2.ScreenshotInstanceRequest.FromString,
                    response_serializer=instance_manager_pb2.ScreenshotInstanceResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/RestartDhu":
                grpc.unary_unary_rpc_method_handler(
                    servicer.RestartDhu,
                    request_deserializer=instance_manager_pb2.RestartDhuRequest.FromString,
                    response_serializer=instance_manager_pb2.RestartDhuResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/DhuCommand":
                grpc.unary_unary_rpc_method_handler(
                    servicer.DhuCommand,
                    request_deserializer=instance_manager_pb2.DhuCommandRequest.FromString,
                    response_serializer=instance_manager_pb2.DhuCommandResponse.SerializeToString,
                ),
        }

    def service(self, handler_call_details):
        return self._method_handlers.get(handler_call_details.method)
