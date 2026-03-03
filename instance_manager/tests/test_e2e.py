"""End-to-end test: full gRPC server with mocked SubprocessRunner."""

import os
import unittest
from unittest.mock import MagicMock

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from unittest.mock import patch as mock_patch

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle, SubprocessRunner
from instance_manager.src.instance_store import RUNNING
from instance_manager.src.server import create_server

_FAKE_PNG = b"\x89PNG-fake-screenshot"


class FakeRunner(SubprocessRunner):
    """Subprocess runner that simulates successful emulator lifecycle."""

    def run(self, args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        if "getprop" in args and "sys.boot_completed" in args:
            result.stdout = "1"

        # When screenshot command is echoed into the pipe, create the file.
        if args and args[0] == "bash" and len(args) > 2:
            cmd_str = args[-1]
            if "screenshot" in cmd_str and ">" in cmd_str and "screencap" not in cmd_str:
                # Parse: echo "screenshot /tmp/dhu_X_screenshot.png" > pipe
                parts = cmd_str.split("screenshot ", 1)
                if len(parts) == 2:
                    path = parts[1].split('"')[0].strip()
                    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(_FAKE_PNG)
            elif "screencap" in cmd_str:
                # Parse: adb -s ... exec-out screencap -p > /tmp/emu_X_screenshot.png
                parts = cmd_str.split("> ")
                if len(parts) >= 2:
                    path = parts[-1].strip()
                    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(_FAKE_PNG)

        return result

    def popen(self, args, **kwargs):
        proc = MagicMock()
        proc.pid = 99999
        proc.poll.return_value = None  # alive
        proc.wait.return_value = 0

        # When DHU is launched, create the log file with "connected".
        if args and args[0] == "bash" and len(args) > 2:
            cmd_str = args[-1]
            if "desktop-head-unit" in cmd_str:
                # Extract log path from "... > /tmp/dhu_X.log 2>&1"
                parts = cmd_str.split("> ")
                if len(parts) >= 2:
                    log_path = parts[-1].replace("2>&1", "").strip()
                    os.makedirs(os.path.dirname(log_path) or "/tmp", exist_ok=True)
                    with open(log_path, "w") as f:
                        f.write("DHU connected\nVerify returned: ok\n")

        return proc


class E2ETest(unittest.TestCase):

    def setUp(self):
        import socket
        sock = socket.socket()
        sock.bind(("", 0))
        free_port = sock.getsockname()[1]
        sock.close()

        self._gpu_patch = mock_patch.object(
            EmulatorLifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect",
        )
        self._gpu_patch.start()

        self.grpc_server, self.http_thread, self.store = create_server(
            grpc_port=free_port, http_port=0, max_slots=4, runner=FakeRunner(),
        )
        self.grpc_server.start()
        self.channel = grpc.insecure_channel(f"localhost:{free_port}")

    def tearDown(self):
        self.channel.close()
        self.grpc_server.stop(0)
        self._gpu_patch.stop()
        # Clean up temp files created by FakeRunner
        import glob
        for pattern in ["/tmp/dhu_*"]:
            for path in glob.glob(pattern):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _call(self, method, request):
        service = "vanpilot.v1.InstanceManagerService"
        resp_map = {
            "CreateInstance": instance_manager_pb2.CreateInstanceResponse,
            "DestroyInstance": instance_manager_pb2.DestroyInstanceResponse,
            "ListInstances": instance_manager_pb2.ListInstancesResponse,
            "GetInstance": instance_manager_pb2.GetInstanceResponse,
            "ScreenshotInstance": instance_manager_pb2.ScreenshotInstanceResponse,
            "RestartDhu": instance_manager_pb2.RestartDhuResponse,
            "DhuCommand": instance_manager_pb2.DhuCommandResponse,
        }
        resp_type = resp_map[method]
        return self.channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=type(request).SerializeToString,
            response_deserializer=resp_type.FromString,
        )(request)

    def test_create_list_screenshot_restart_destroy_cycle(self):
        # Create
        resp = self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="e2e-test"),
        )
        self.assertEqual(resp.instance.name, "e2e-test")

        # List
        list_resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(list_resp.instances), 1)

        # Screenshot
        snap_resp = self._call(
            "ScreenshotInstance",
            instance_manager_pb2.ScreenshotInstanceRequest(name="e2e-test"),
        )
        self.assertEqual(snap_resp.dhu_screenshot_png, _FAKE_PNG)
        self.assertEqual(snap_resp.emulator_screenshot_png, _FAKE_PNG)
        self.assertGreater(snap_resp.captured_at_ms, 0)

        # DHU command (no screenshot)
        cmd_resp = self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="e2e-test", command="keycode home",
            ),
        )
        self.assertGreater(cmd_resp.executed_at_ms, 0)
        self.assertEqual(cmd_resp.screenshot_png, b"")

        # DHU command (with screenshot)
        cmd_ss_resp = self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="e2e-test", command="tap 300 430",
                capture_screenshot=True,
            ),
        )
        self.assertGreater(cmd_ss_resp.executed_at_ms, 0)
        self.assertEqual(cmd_ss_resp.screenshot_png, _FAKE_PNG)

        # Restart DHU
        restart_resp = self._call(
            "RestartDhu",
            instance_manager_pb2.RestartDhuRequest(name="e2e-test"),
        )
        self.assertEqual(restart_resp.instance.name, "e2e-test")
        self.assertEqual(restart_resp.instance.state, RUNNING)
        self.assertTrue(len(restart_resp.instance.last_screenshot_png) > 0)

        # Destroy
        self._call(
            "DestroyInstance",
            instance_manager_pb2.DestroyInstanceRequest(name="e2e-test"),
        )

        # Verify empty
        list_resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(list_resp.instances), 0)

    def test_create_destroy_reuse_name(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="reuse"),
        )
        self._call(
            "DestroyInstance",
            instance_manager_pb2.DestroyInstanceRequest(name="reuse"),
        )
        # Should succeed — name is available again
        resp = self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="reuse"),
        )
        self.assertEqual(resp.instance.name, "reuse")


if __name__ == "__main__":
    unittest.main()
