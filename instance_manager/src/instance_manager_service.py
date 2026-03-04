"""gRPC servicer for InstanceManagerService."""

from __future__ import annotations

import re
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
from instance_manager.src.video_capture import VideoCaptureManager

_DEFAULT_AVD = "vanpilot_pixel9pro_api36"
_DEFAULT_SNAPSHOT = "aa_ready"

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


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
        video_capture: VideoCaptureManager | None = None,
    ) -> None:
        self._store = store
        self._lifecycle = lifecycle
        self._port_allocator = port_allocator
        self._video_capture = video_capture or VideoCaptureManager()

    def CreateInstance(self, request, context):
        name = request.name
        if not name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")
        if not _SAFE_NAME_RE.match(name):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Invalid name '{name}': must match [a-zA-Z0-9][a-zA-Z0-9._-]*",
            )

        if self._store.get(name) is not None:
            context.abort(
                grpc.StatusCode.ALREADY_EXISTS,
                f"Instance '{name}' already exists",
            )

        avd_name = request.avd_name or _DEFAULT_AVD
        snapshot_name = request.snapshot_name or _DEFAULT_SNAPSHOT

        if not _SAFE_NAME_RE.match(avd_name):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Invalid avd_name '{avd_name}'",
            )
        if not _SAFE_NAME_RE.match(snapshot_name):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Invalid snapshot_name '{snapshot_name}'",
            )

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
            self._store.remove(name)
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

    def InstallApk(self, request, context):
        if not request.apk_data:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "apk_data is required"
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
            self._lifecycle.install_apk(record, request.apk_data)

            if request.restart_dhu:
                record = self._lifecycle.restart_dhu(record)
            else:
                record = self._store.get(request.name)

            return instance_manager_pb2.InstallApkResponse(
                instance=_record_to_proto(record),
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def AdbShell(self, request, context):
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
            exit_code, stdout, stderr = self._lifecycle.adb_shell(
                record, list(request.args), request.timeout_s,
            )
            return instance_manager_pb2.AdbShellResponse(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def AdbPush(self, request, context):
        if not request.data:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "data is required"
            )
        if not request.remote_path:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "remote_path is required"
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
            self._lifecycle.adb_push(record, request.data, request.remote_path)
            return instance_manager_pb2.AdbPushResponse()
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def AdbPull(self, request, context):
        if not request.remote_path:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "remote_path is required"
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
            data = self._lifecycle.adb_pull(record, request.remote_path)
            return instance_manager_pb2.AdbPullResponse(data=data)
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def StartVideoCapture(self, request, context):
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
        if not record.pipe_path:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Instance '{request.name}' has no pipe path",
            )

        try:
            capture_id = self._video_capture.start(
                instance_name=request.name,
                pipe_path=record.pipe_path,
                target_fps=request.target_fps,
                max_duration_s=request.max_duration_s,
            )
            return instance_manager_pb2.StartVideoCaptureResponse(
                capture_id=capture_id,
            )
        except RuntimeError as e:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, str(e))
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def StopVideoCapture(self, request, context):
        record = self._store.get(request.name)
        if record is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Instance '{request.name}' not found",
            )

        result = self._video_capture.stop(request.name)
        if result is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"No active video capture for '{request.name}'",
            )

        return instance_manager_pb2.StopVideoCaptureResponse(
            video_mp4=result.video_mp4,
            frame_count=result.frame_count,
            actual_fps=result.actual_fps,
            duration_ms=result.duration_ms,
            capture_id=result.capture_id,
        )


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
            f"/{self._SERVICE}/InstallApk":
                grpc.unary_unary_rpc_method_handler(
                    servicer.InstallApk,
                    request_deserializer=instance_manager_pb2.InstallApkRequest.FromString,
                    response_serializer=instance_manager_pb2.InstallApkResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/AdbShell":
                grpc.unary_unary_rpc_method_handler(
                    servicer.AdbShell,
                    request_deserializer=instance_manager_pb2.AdbShellRequest.FromString,
                    response_serializer=instance_manager_pb2.AdbShellResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/AdbPush":
                grpc.unary_unary_rpc_method_handler(
                    servicer.AdbPush,
                    request_deserializer=instance_manager_pb2.AdbPushRequest.FromString,
                    response_serializer=instance_manager_pb2.AdbPushResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/AdbPull":
                grpc.unary_unary_rpc_method_handler(
                    servicer.AdbPull,
                    request_deserializer=instance_manager_pb2.AdbPullRequest.FromString,
                    response_serializer=instance_manager_pb2.AdbPullResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/StartVideoCapture":
                grpc.unary_unary_rpc_method_handler(
                    servicer.StartVideoCapture,
                    request_deserializer=instance_manager_pb2.StartVideoCaptureRequest.FromString,
                    response_serializer=instance_manager_pb2.StartVideoCaptureResponse.SerializeToString,
                ),
            f"/{self._SERVICE}/StopVideoCapture":
                grpc.unary_unary_rpc_method_handler(
                    servicer.StopVideoCapture,
                    request_deserializer=instance_manager_pb2.StopVideoCaptureRequest.FromString,
                    response_serializer=instance_manager_pb2.StopVideoCaptureResponse.SerializeToString,
                ),
        }

    def service(self, handler_call_details):
        return self._method_handlers.get(handler_call_details.method)
