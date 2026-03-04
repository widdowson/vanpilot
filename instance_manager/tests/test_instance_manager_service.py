"""Tests for InstanceManagerServicer with in-process gRPC."""

import time
import unittest
from concurrent import futures
from unittest.mock import MagicMock, patch

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle
from instance_manager.src.instance_manager_service import (
    add_instance_manager_service_to_server,
)
from instance_manager.src.instance_store import InstanceStore, RUNNING, CREATING
from instance_manager.src.port_allocator import PortAllocator
from instance_manager.src.video_capture import (
    CaptureResult,
    VideoCaptureManager,
)


class InstanceManagerServiceTest(unittest.TestCase):

    def setUp(self):
        self.store = InstanceStore()
        self.port_allocator = PortAllocator(max_slots=4)
        self.lifecycle = MagicMock(spec=EmulatorLifecycle)

        # Make lifecycle.create return a record with RUNNING state
        def fake_create(name, avd_name, snapshot_name, headful, ports):
            self.store.update(name, state=RUNNING)
            return self.store.get(name)

        self.lifecycle.create.side_effect = fake_create
        self.lifecycle.screenshot.return_value = b"fake-png-bytes"
        self.lifecycle.emulator_screenshot_to_bytes.return_value = b"fake-emu-png"

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        add_instance_manager_service_to_server(
            self.server, self.store, self.lifecycle, self.port_allocator,
        )
        port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(0)

    def _call(self, method, request):
        """Invoke an RPC using the channel directly."""
        service = "vanpilot.v1.InstanceManagerService"
        req_type = type(request)
        resp_map = {
            "CreateInstance": instance_manager_pb2.CreateInstanceResponse,
            "DestroyInstance": instance_manager_pb2.DestroyInstanceResponse,
            "ListInstances": instance_manager_pb2.ListInstancesResponse,
            "GetInstance": instance_manager_pb2.GetInstanceResponse,
            "ScreenshotInstance": instance_manager_pb2.ScreenshotInstanceResponse,
            "RestartDhu": instance_manager_pb2.RestartDhuResponse,
            "DhuCommand": instance_manager_pb2.DhuCommandResponse,
            "StartVideoCapture": instance_manager_pb2.StartVideoCaptureResponse,
            "StopVideoCapture": instance_manager_pb2.StopVideoCaptureResponse,
            "InstallApk": instance_manager_pb2.InstallApkResponse,
            "AdbShell": instance_manager_pb2.AdbShellResponse,
            "AdbPush": instance_manager_pb2.AdbPushResponse,
            "AdbPull": instance_manager_pb2.AdbPullResponse,
        }
        resp_type = resp_map[method]
        return self.channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=req_type.SerializeToString,
            response_deserializer=resp_type.FromString,
        )(request)

    def test_create_instance_with_defaults(self):
        resp = self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="agent-1"),
        )
        self.assertEqual(resp.instance.name, "agent-1")
        self.assertEqual(resp.instance.state, RUNNING)
        self.assertEqual(resp.instance.emulator_console_port, 5554)
        self.lifecycle.create.assert_called_once()
        call_kwargs = self.lifecycle.create.call_args
        self.assertEqual(call_kwargs.kwargs.get("avd_name") or call_kwargs[1].get("avd_name", call_kwargs[0][1]),
                         "vanpilot_pixel9pro_api36")

    def test_create_instance_duplicate_name(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="dup"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "CreateInstance",
                instance_manager_pb2.CreateInstanceRequest(name="dup"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.ALREADY_EXISTS)

    def test_destroy_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="to-destroy"),
        )
        self._call(
            "DestroyInstance",
            instance_manager_pb2.DestroyInstanceRequest(name="to-destroy"),
        )
        self.lifecycle.destroy.assert_called_once()
        # Should be gone from store
        resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(resp.instances), 0)

    def test_destroy_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DestroyInstance",
                instance_manager_pb2.DestroyInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_list_instances(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="a"),
        )
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="b"),
        )
        resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(resp.instances), 2)
        names = {i.name for i in resp.instances}
        self.assertEqual(names, {"a", "b"})

    def test_get_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="test"),
        )
        resp = self._call(
            "GetInstance",
            instance_manager_pb2.GetInstanceRequest(name="test"),
        )
        self.assertEqual(resp.instance.name, "test")

    def test_get_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "GetInstance",
                instance_manager_pb2.GetInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_screenshot_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="snap"),
        )
        resp = self._call(
            "ScreenshotInstance",
            instance_manager_pb2.ScreenshotInstanceRequest(name="snap"),
        )
        self.assertEqual(resp.dhu_screenshot_png, b"fake-png-bytes")
        self.assertEqual(resp.emulator_screenshot_png, b"fake-emu-png")
        self.assertGreater(resp.captured_at_ms, 0)

    def test_screenshot_not_running(self):
        # Create an instance but leave it in CREATING state
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "ScreenshotInstance",
                instance_manager_pb2.ScreenshotInstanceRequest(name="creating"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_screenshot_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "ScreenshotInstance",
                instance_manager_pb2.ScreenshotInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_restart_dhu(self):
        # Set up restart_dhu mock to return the updated record
        def fake_restart_dhu(record):
            return self.store.get(record.name)

        self.lifecycle.restart_dhu = MagicMock(side_effect=fake_restart_dhu)

        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="restart-test"),
        )
        resp = self._call(
            "RestartDhu",
            instance_manager_pb2.RestartDhuRequest(name="restart-test"),
        )
        self.assertEqual(resp.instance.name, "restart-test")
        self.lifecycle.restart_dhu.assert_called_once()

    def test_restart_dhu_not_running(self):
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "RestartDhu",
                instance_manager_pb2.RestartDhuRequest(name="creating"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_restart_dhu_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "RestartDhu",
                instance_manager_pb2.RestartDhuRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_dhu_command(self):
        self.lifecycle.dhu_command = MagicMock(return_value=b"")
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="cmd-test"),
        )
        resp = self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="cmd-test", command="keycode home",
            ),
        )
        self.assertGreater(resp.executed_at_ms, 0)
        self.lifecycle.dhu_command.assert_called_once()

    def test_dhu_command_screenshot_updates_store(self):
        self.lifecycle.dhu_command = MagicMock(return_value=b"fresh-png")
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="cache-test"),
        )
        self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="cache-test", command="tap 100 200",
                capture_screenshot=True,
            ),
        )
        record = self.store.get("cache-test")
        self.assertEqual(record.last_screenshot_png, b"fresh-png")
        self.assertIsNotNone(record.last_screenshot_at_ms)

    def test_dhu_command_not_running(self):
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="creating", command="keycode home",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_dhu_command_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="nope", command="keycode home",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_dhu_command_empty_command(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-cmd"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="empty-cmd", command="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_start_video_capture(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="video-test"),
        )
        self.store.update("video-test", pipe_path="/tmp/fake_pipe")

        resp = self._call(
            "StartVideoCapture",
            instance_manager_pb2.StartVideoCaptureRequest(
                name="video-test", target_fps=2,
            ),
        )
        self.assertIsInstance(resp.capture_id, str)
        self.assertGreater(len(resp.capture_id), 0)

    def test_start_video_capture_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "StartVideoCapture",
                instance_manager_pb2.StartVideoCaptureRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_start_video_capture_not_running(self):
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "StartVideoCapture",
                instance_manager_pb2.StartVideoCaptureRequest(name="creating"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_start_video_capture_duplicate(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="dup-video"),
        )
        self.store.update("dup-video", pipe_path="/tmp/fake_pipe")

        self._call(
            "StartVideoCapture",
            instance_manager_pb2.StartVideoCaptureRequest(name="dup-video"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "StartVideoCapture",
                instance_manager_pb2.StartVideoCaptureRequest(name="dup-video"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.ALREADY_EXISTS)

    def test_stop_video_capture_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "StopVideoCapture",
                instance_manager_pb2.StopVideoCaptureRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_stop_video_capture_not_started(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="no-video"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "StopVideoCapture",
                instance_manager_pb2.StopVideoCaptureRequest(name="no-video"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_start_stop_video_capture_roundtrip(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="roundtrip"),
        )
        self.store.update("roundtrip", pipe_path="/tmp/fake_pipe")

        start_resp = self._call(
            "StartVideoCapture",
            instance_manager_pb2.StartVideoCaptureRequest(
                name="roundtrip", target_fps=2,
            ),
        )
        time.sleep(0.1)

        stop_resp = self._call(
            "StopVideoCapture",
            instance_manager_pb2.StopVideoCaptureRequest(name="roundtrip"),
        )
        self.assertEqual(stop_resp.capture_id, start_resp.capture_id)
        self.assertGreaterEqual(stop_resp.duration_ms, 0)

    # ---- InstallApk tests ----

    def test_install_apk_with_restart(self):
        """InstallApk installs and restarts DHU when restart_dhu=True."""
        self.lifecycle.install_apk = MagicMock()

        def fake_restart(record):
            return self.store.get(record.name)
        self.lifecycle.restart_dhu = MagicMock(side_effect=fake_restart)

        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="apk-test"),
        )
        resp = self._call(
            "InstallApk",
            instance_manager_pb2.InstallApkRequest(
                name="apk-test",
                apk_data=b"fake-apk-bytes",
                restart_dhu=True,
            ),
        )
        self.assertEqual(resp.instance.name, "apk-test")
        self.lifecycle.install_apk.assert_called_once()
        self.lifecycle.restart_dhu.assert_called_once()

    def test_install_apk_without_restart(self):
        """InstallApk skips DHU restart when restart_dhu=False."""
        self.lifecycle.install_apk = MagicMock()
        self.lifecycle.restart_dhu = MagicMock()

        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="no-restart"),
        )
        resp = self._call(
            "InstallApk",
            instance_manager_pb2.InstallApkRequest(
                name="no-restart",
                apk_data=b"fake-apk",
                restart_dhu=False,
            ),
        )
        self.assertEqual(resp.instance.name, "no-restart")
        self.lifecycle.install_apk.assert_called_once()
        self.lifecycle.restart_dhu.assert_not_called()

    def test_install_apk_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "InstallApk",
                instance_manager_pb2.InstallApkRequest(
                    name="nope", apk_data=b"apk",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_install_apk_not_running(self):
        self.store.create("creating", 5556, 5557, 5278, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "InstallApk",
                instance_manager_pb2.InstallApkRequest(
                    name="creating", apk_data=b"apk",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_install_apk_empty_data(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-apk"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "InstallApk",
                instance_manager_pb2.InstallApkRequest(
                    name="empty-apk", apk_data=b"",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)


    # ---- AdbShell / AdbPush / AdbPull tests ----

    def test_adb_shell_returns_stdout_stderr(self):
        """AdbShell returns exit_code, stdout, and stderr from lifecycle."""
        self.lifecycle.adb_shell = MagicMock(return_value=(0, "package:com.vanpilot.auto\n", ""))
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="adb-test"),
        )
        resp = self._call(
            "AdbShell",
            instance_manager_pb2.AdbShellRequest(
                name="adb-test",
                args=["pm", "list", "packages"],
                timeout_s=10,
            ),
        )
        self.assertEqual(resp.exit_code, 0)
        self.assertEqual(resp.stdout, "package:com.vanpilot.auto\n")
        self.assertEqual(resp.stderr, "")
        self.lifecycle.adb_shell.assert_called_once()

    def test_adb_shell_rejects_missing_instance(self):
        """AdbShell returns NOT_FOUND for nonexistent instance."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbShell",
                instance_manager_pb2.AdbShellRequest(
                    name="nope", args=["echo", "hi"],
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_adb_shell_rejects_not_running(self):
        """AdbShell returns FAILED_PRECONDITION if instance not running."""
        self.store.create("creating", 5556, 5557, 5278, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbShell",
                instance_manager_pb2.AdbShellRequest(
                    name="creating", args=["echo", "hi"],
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_adb_push_and_pull(self):
        """AdbPush and AdbPull round-trip through the service."""
        self.lifecycle.adb_push = MagicMock()
        self.lifecycle.adb_pull = MagicMock(return_value=b"file-contents")

        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="push-pull"),
        )

        # Push
        self._call(
            "AdbPush",
            instance_manager_pb2.AdbPushRequest(
                name="push-pull",
                data=b"file-contents",
                remote_path="/sdcard/test.txt",
            ),
        )
        self.lifecycle.adb_push.assert_called_once()

        # Pull
        resp = self._call(
            "AdbPull",
            instance_manager_pb2.AdbPullRequest(
                name="push-pull",
                remote_path="/sdcard/test.txt",
            ),
        )
        self.assertEqual(resp.data, b"file-contents")
        self.lifecycle.adb_pull.assert_called_once()

    def test_adb_shell_rejects_empty_args(self):
        """AdbShell returns INVALID_ARGUMENT for empty args."""
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-args"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbShell",
                instance_manager_pb2.AdbShellRequest(
                    name="empty-args", args=[],
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_adb_push_rejects_missing_instance(self):
        """AdbPush returns NOT_FOUND for nonexistent instance."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPush",
                instance_manager_pb2.AdbPushRequest(
                    name="nope", data=b"x", remote_path="/sdcard/x",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_adb_push_rejects_not_running(self):
        """AdbPush returns FAILED_PRECONDITION if instance not running."""
        self.store.create("creating2", 5558, 5559, 5279, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPush",
                instance_manager_pb2.AdbPushRequest(
                    name="creating2", data=b"x", remote_path="/sdcard/x",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_adb_push_empty_remote_path(self):
        """AdbPush rejects empty remote_path."""
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="no-remote"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPush",
                instance_manager_pb2.AdbPushRequest(
                    name="no-remote", data=b"x", remote_path="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_adb_pull_rejects_missing_instance(self):
        """AdbPull returns NOT_FOUND for nonexistent instance."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPull",
                instance_manager_pb2.AdbPullRequest(
                    name="nope", remote_path="/sdcard/x",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_adb_pull_rejects_not_running(self):
        """AdbPull returns FAILED_PRECONDITION if instance not running."""
        self.store.create("creating3", 5560, 5561, 5280, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPull",
                instance_manager_pb2.AdbPullRequest(
                    name="creating3", remote_path="/sdcard/x",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_adb_push_empty_data(self):
        """AdbPush rejects empty data."""
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-push"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPush",
                instance_manager_pb2.AdbPushRequest(
                    name="empty-push", data=b"", remote_path="/sdcard/x",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_adb_pull_empty_path(self):
        """AdbPull rejects empty remote_path."""
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-pull"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "AdbPull",
                instance_manager_pb2.AdbPullRequest(
                    name="empty-pull", remote_path="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)


if __name__ == "__main__":
    unittest.main()
