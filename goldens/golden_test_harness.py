"""Test harness for automated golden tests using the instance manager.

Connects to a running InstanceManagerService to create emulator+DHU pairs,
install the VanPilot APK, capture screenshots, and compare against goldens.

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to the VanPilot APK (optional — skips install if unset)
  GOLDEN_TOLERANCE: Per-channel pixel tolerance (default 5)
"""

import os
import subprocess
import time
import unittest
from typing import Optional

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from goldens.golden_diff import compare_golden

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
        self._channel = grpc.insecure_channel(addr)

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


def install_apk(adb_port: int, apk_path: str) -> None:
    """Install an APK on the emulator via its ADB port."""
    serial = f"localhost:{adb_port}"
    subprocess.run(
        ["adb", "connect", serial],
        capture_output=True, text=True, timeout=10,
    )
    subprocess.run(
        ["adb", "-s", serial, "install", "-r", apk_path],
        capture_output=True, text=True, timeout=120, check=True,
    )


def launch_vanpilot_app(adb_port: int) -> None:
    """Launch the VanPilot car app service on the emulator."""
    serial = f"localhost:{adb_port}"
    try:
        subprocess.run(
            ["adb", "-s", serial, "shell", "am", "start", "-n",
             "com.vanpilot.auto/.VanPilotCarAppService"],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.CalledProcessError:
        pass  # Service will be started by DHU


def capture_emulator_screenshot(adb_port: int) -> bytes:
    """Capture screenshot via adb screencap and return PNG bytes."""
    serial = f"localhost:{adb_port}"
    remote = "/sdcard/golden_harness_screenshot.png"
    local = f"/tmp/golden_harness_{adb_port}.png"

    subprocess.run(
        ["adb", "-s", serial, "shell", "screencap", "-p", remote],
        capture_output=True, text=True, timeout=30, check=True,
    )
    subprocess.run(
        ["adb", "-s", serial, "pull", remote, local],
        capture_output=True, text=True, timeout=60, check=True,
    )
    subprocess.run(
        ["adb", "-s", serial, "shell", "rm", remote],
        capture_output=True, timeout=10,
    )

    with open(local, "rb") as f:
        return f.read()


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

        # Install APK and launch if configured
        if VANPILOT_APK:
            install_apk(cls._instance_info.adb_port, VANPILOT_APK)
            launch_vanpilot_app(cls._instance_info.adb_port)
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
        """Capture a DHU screenshot via the instance manager."""
        resp = self._client.screenshot_instance(self.instance_name)
        return resp.dhu_screenshot_png

    def capture_emulator_screenshot(self) -> bytes:
        """Capture an emulator screenshot via adb screencap."""
        return capture_emulator_screenshot(self._instance_info.adb_port)

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
