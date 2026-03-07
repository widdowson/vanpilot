"""Test harness for automated golden tests using the instance manager.

Connects to a running InstanceManagerService to create emulator+DHU pairs,
install the VanPilot APK, capture screenshots, and compare against goldens.

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to the VanPilot APK (optional — skips install if unset)
  GOLDEN_TOLERANCE: Per-channel pixel tolerance (default 5)
"""

import os
import time
import unittest
from typing import Optional

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from goldens.golden_diff import compare_golden, crop_to_app_pane
from instance_manager.src import MAX_MESSAGE_BYTES

INSTANCE_MANAGER_ADDR = os.environ.get("INSTANCE_MANAGER_ADDR", "localhost:50061")
VANPILOT_APK = os.environ.get("VANPILOT_APK", "")
GOLDEN_TOLERANCE = int(os.environ.get("GOLDEN_TOLERANCE", "5"))
RENDER_SETTLE_TIME = 10  # seconds to wait after app launch


def _service_method(method, request, response_type, channel):
    """Call an InstanceManagerService RPC via raw channel."""
    service = "vanpilot.v1.InstanceManagerService"
    return channel.unary_unary(
        f"/{service}/{method}",
        request_serializer=type(request).SerializeToString,
        response_deserializer=response_type.FromString,
    )(request)


class InstanceManagerClient:
    """gRPC client for the InstanceManagerService."""

    def __init__(self, addr: str = INSTANCE_MANAGER_ADDR):
        self._channel = grpc.insecure_channel(
            addr,
            options=[
                ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
                ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
            ],
        )

    def close(self):
        self._channel.close()

    def create_instance(
        self,
        name: str,
        headful: bool = False,
        avd_name: str = "",
        snapshot_name: str = "",
    ) -> instance_manager_pb2.CreateInstanceResponse:
        req = instance_manager_pb2.CreateInstanceRequest(
            name=name, headful=headful,
            avd_name=avd_name, snapshot_name=snapshot_name,
        )
        return _service_method(
            "CreateInstance", req,
            instance_manager_pb2.CreateInstanceResponse,
            self._channel,
        )

    def destroy_instance(self, name: str) -> None:
        req = instance_manager_pb2.DestroyInstanceRequest(name=name)
        _service_method(
            "DestroyInstance", req,
            instance_manager_pb2.DestroyInstanceResponse,
            self._channel,
        )

    def get_instance(
        self, name: str,
    ) -> instance_manager_pb2.GetInstanceResponse:
        req = instance_manager_pb2.GetInstanceRequest(name=name)
        return _service_method(
            "GetInstance", req,
            instance_manager_pb2.GetInstanceResponse,
            self._channel,
        )

    def screenshot_instance(
        self, name: str,
    ) -> instance_manager_pb2.ScreenshotInstanceResponse:
        req = instance_manager_pb2.ScreenshotInstanceRequest(name=name)
        return _service_method(
            "ScreenshotInstance", req,
            instance_manager_pb2.ScreenshotInstanceResponse,
            self._channel,
        )

    def dhu_command(
        self,
        name: str,
        command: str,
        capture_screenshot: bool = False,
    ) -> instance_manager_pb2.DhuCommandResponse:
        req = instance_manager_pb2.DhuCommandRequest(
            name=name,
            command=command,
            capture_screenshot=capture_screenshot,
        )
        return _service_method(
            "DhuCommand", req,
            instance_manager_pb2.DhuCommandResponse,
            self._channel,
        )

    def install_apk(
        self,
        name: str,
        apk_data: bytes,
        restart_dhu: bool = True,
    ) -> instance_manager_pb2.InstallApkResponse:
        req = instance_manager_pb2.InstallApkRequest(
            name=name,
            apk_data=apk_data,
            restart_dhu=restart_dhu,
        )
        return _service_method(
            "InstallApk", req,
            instance_manager_pb2.InstallApkResponse,
            self._channel,
        )

    def restart_dhu(
        self, name: str,
    ) -> instance_manager_pb2.RestartDhuResponse:
        req = instance_manager_pb2.RestartDhuRequest(name=name)
        return _service_method(
            "RestartDhu", req,
            instance_manager_pb2.RestartDhuResponse,
            self._channel,
        )

    def adb_shell(
        self,
        name: str,
        args: list[str],
        timeout_s: int = 30,
    ) -> instance_manager_pb2.AdbShellResponse:
        req = instance_manager_pb2.AdbShellRequest(
            name=name,
            args=args,
            timeout_s=timeout_s,
        )
        return _service_method(
            "AdbShell", req,
            instance_manager_pb2.AdbShellResponse,
            self._channel,
        )


def launch_vanpilot_via_dhu(client: InstanceManagerClient, name: str) -> None:
    """Launch VanPilot on the DHU via the app launcher grid.

    Car App Library apps cannot be started with `am start`. Instead we open
    the DHU app launcher and tap VanPilot's icon in the grid.
    See docs/app-launch.md for the full reference.
    """
    # Open app launcher
    client.dhu_command(name, "keycode home")
    time.sleep(2)
    # Tap VanPilot icon — Row 3, Col 1 in the launcher grid (1920x1080 coords).
    # First tap selects/highlights the icon; second tap confirms the launch.
    client.dhu_command(name, "tap 200 390")
    time.sleep(1)
    client.dhu_command(name, "tap 200 390")
    time.sleep(RENDER_SETTLE_TIME)


class GoldenTestCase(unittest.TestCase):
    """Base class for golden tests that use the instance manager.

    Subclasses should set `instance_name` as a class variable or in setUp.
    The instance is created in setUpClass and destroyed in tearDownClass.
    """

    instance_name: str = ""
    _client: Optional[InstanceManagerClient] = None
    _instance_info: Optional[object] = None

    @classmethod
    def setUpClass(cls):
        if not cls.instance_name:
            cls.instance_name = f"golden-{cls.__name__.lower()}"

        cls._client = InstanceManagerClient()
        try:
            resp = cls._client.create_instance(name=cls.instance_name)
            cls._instance_info = resp.instance
        except grpc.RpcError as e:
            cls._client.close()
            raise unittest.SkipTest(
                f"Cannot create instance: {e.details()}"
            ) from e

        # Install APK via IM gRPC (not raw adb) and launch via DHU commands
        if VANPILOT_APK:
            with open(VANPILOT_APK, "rb") as f:
                apk_data = f.read()
            cls._client.install_apk(
                cls.instance_name, apk_data, restart_dhu=True,
            )
            launch_vanpilot_via_dhu(cls._client, cls.instance_name)
            time.sleep(RENDER_SETTLE_TIME)

    @classmethod
    def tearDownClass(cls):
        if cls._client:
            try:
                cls._client.destroy_instance(cls.instance_name)
            except grpc.RpcError:
                pass
            cls._client.close()

    def capture_dhu_screenshot(self) -> bytes:
        """Capture a DHU screenshot and crop to the app pane (1832x1056)."""
        resp = self._client.screenshot_instance(self.instance_name)
        return crop_to_app_pane(resp.dhu_screenshot_png)

    def capture_raw_dhu_screenshot(self) -> bytes:
        """Capture a raw 1920x1080 DHU screenshot without cropping."""
        resp = self._client.screenshot_instance(self.instance_name)
        return resp.dhu_screenshot_png

    def dhu_command(self, command: str, capture_screenshot: bool = False):
        """Send a DHU console command."""
        return self._client.dhu_command(
            self.instance_name, command, capture_screenshot,
        )

    def verify_vanpilot_foreground(self):
        """Assert VanPilot is running, not just Maps or the launcher.

        Car App Library apps run inside the Android Auto host process, so
        they may not appear as a resumed activity in `dumpsys activity`.
        We check both `dumpsys activity activities` and `dumpsys activity
        services` for any vanpilot component.
        """
        for dump_target in ["activities", "services"]:
            resp = self._client.adb_shell(
                self.instance_name,
                ["dumpsys", "activity", dump_target],
            )
            if "vanpilot" in resp.stdout.lower():
                return
        # If neither shows vanpilot, capture what we see for debugging
        resp = self._client.adb_shell(
            self.instance_name,
            ["dumpsys", "activity", "services"],
        )
        self.fail(
            "VanPilot is not running. "
            "dumpsys activity services:\n"
            + resp.stdout[:500]
        )

    def save_test_output(self, name: str, data: bytes) -> Optional[str]:
        """Save data to TEST_UNDECLARED_OUTPUTS_DIR for CI artifacts."""
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
        if not undeclared:
            return None
        os.makedirs(undeclared, exist_ok=True)
        path = os.path.join(undeclared, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def assert_matches_golden(
        self,
        actual_png: bytes,
        golden_path: str,
        tolerance: int = GOLDEN_TOLERANCE,
    ) -> None:
        """Assert that actual screenshot matches a golden image file.

        Saves actual, golden, and diff PNGs to test outputs on failure.
        """
        if not os.path.exists(golden_path):
            self.save_test_output("actual.png", actual_png)
            self.skipTest(f"No golden at {golden_path} — run capture first")

        with open(golden_path, "rb") as f:
            golden_png = f.read()

        self.save_test_output("actual.png", actual_png)
        self.save_test_output("golden.png", golden_png)

        match, diff_count, diff_png = compare_golden(
            actual_png, golden_png, tolerance=tolerance,
        )
        if diff_png:
            self.save_test_output("diff.png", diff_png)

        if not match:
            self.fail(
                f"Screenshot does not match golden: {diff_count} pixels differ. "
                f"See diff.png in test outputs."
            )
