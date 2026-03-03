"""Emulator-based golden screenshot test.

This test connects to a running emulator (either via TCP sidecar or native
ADB discovery), captures a screenshot, and compares it against committed
golden images using pixel-by-pixel diffing.

Supports two modes:
  1. Docker sidecar: set EMU_HOST and EMU_PORT env vars
  2. Native emulator: auto-discovered via `adb devices` as emulator-NNNN

This test is tagged "manual" in BUILD.bazel so it only runs when explicitly
requested (not during `bazel test //...`).

Usage:
  # TCP sidecar
  bazel test //goldens:emulator_golden_test --test_env=EMU_HOST=localhost --test_env=EMU_PORT=5555

  # Native emulator (auto-detect)
  bazel test //goldens:emulator_golden_test

  # With video capture (AC-4.2)
  bazel test //goldens:emulator_golden_test --test_arg=--record-video
"""

import os
import subprocess
import sys
import struct
import unittest

# Allow imports from workspace root
sys.path.insert(0, os.path.join(os.environ.get("TEST_SRCDIR", ""), os.environ.get("TEST_WORKSPACE", "")))

from goldens.golden_diff import compare_golden, mask_status_bar, read_png_pixels
from goldens.video_capture import VideoCaptureConfig, VideoCapture


EMU_HOST = os.environ.get("EMU_HOST", "")
EMU_PORT = os.environ.get("EMU_PORT", "")
BOOT_TIMEOUT = 300  # 5 minutes

GOLDEN_DIR = os.path.join(
    os.environ.get("TEST_SRCDIR", ""),
    os.environ.get("TEST_WORKSPACE", ""),
    "goldens",
    "phase9",
)

# Video capture config parsed from test args (AC-4.1, AC-4.2).
# Enabled via: bazel test //goldens:emulator_golden_test --test_arg=--record-video
VIDEO_CONFIG = VideoCaptureConfig.from_args(sys.argv[1:])

# Strip --record-video* args so unittest.main() doesn't choke on them.
sys.argv = [a for a in sys.argv if not a.startswith("--record-video")]

VIDEO_CAPTURE: VideoCapture  # initialized after emulator discovery (needs serial)


def _find_emulator_serial() -> str | None:
    """Find an available emulator, trying native first then TCP.

    Returns:
        ADB serial string, or None if no emulator is available.
    """
    # Try native emulator discovery first
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith("emulator-") and parts[1] == "device":
                return parts[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fall back to TCP connect if EMU_HOST/EMU_PORT are set
    if EMU_HOST:
        addr = f"{EMU_HOST}:{EMU_PORT or '5555'}"
        try:
            subprocess.run(
                ["adb", "connect", addr],
                capture_output=True, text=True, timeout=10,
            )
            result = subprocess.run(
                ["adb", "-s", addr, "shell", "getprop", "sys.boot_completed"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip() == "1":
                return addr
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return None


EMU_SERIAL = _find_emulator_serial()

# Now that we know the emulator serial, configure video capture to target it.
# VideoCapture defaults to "localhost:5555" which only works for TCP sidecar;
# native emulators appear as "emulator-NNNN" and need the serial passed directly.
if EMU_SERIAL and VIDEO_CONFIG.enabled:
    VIDEO_CONFIG.adb_serial = EMU_SERIAL
VIDEO_CAPTURE = VideoCapture(VIDEO_CONFIG)


def _adb(*args: str, timeout: int = 30) -> str:
    """Run an ADB command targeting the discovered emulator."""
    cmd = ["adb", "-s", EMU_SERIAL] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()


def _adb_check(*args: str, timeout: int = 30) -> str:
    """Run an ADB command, raising on failure."""
    cmd = ["adb", "-s", EMU_SERIAL] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=True
    )
    return result.stdout.strip()


def _capture_screenshot(output_path: str) -> None:
    """Capture screenshot from emulator via adb screencap.

    The top 100 rows (status bar) are masked to hot pink to eliminate
    clock/battery jitter between captures.
    """
    remote = "/sdcard/golden_test_screenshot.png"
    _adb_check("shell", "screencap", "-p", remote)
    _adb_check("pull", remote, output_path, timeout=60)
    _adb_check("shell", "rm", remote)

    with open(output_path, "rb") as f:
        raw = f.read()
    masked = mask_status_bar(raw, rows=100)
    with open(output_path, "wb") as f:
        f.write(masked)


@unittest.skipUnless(
    EMU_SERIAL is not None,
    "No emulator available (set EMU_HOST/EMU_PORT for TCP, or start a native emulator)",
)
class EmulatorGoldenTest(unittest.TestCase):
    """Compare live emulator screenshots against committed goldens."""

    @classmethod
    def setUpClass(cls) -> None:
        VIDEO_CAPTURE.start()

    @classmethod
    def tearDownClass(cls) -> None:
        VIDEO_CAPTURE.stop("emulator_golden")

    def _save_undeclared(self, name: str, data: bytes) -> str | None:
        """Save data to TEST_UNDECLARED_OUTPUTS_DIR for CI artifacts."""
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
        if not undeclared:
            return None
        os.makedirs(undeclared, exist_ok=True)
        path = os.path.join(undeclared, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_emulator_screenshot_captures_valid_png(self):
        """Verify we can capture a valid PNG from the emulator."""
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp")
        os.makedirs(undeclared, exist_ok=True)
        output = os.path.join(undeclared, "emulator_capture.png")

        _capture_screenshot(output)

        self.assertTrue(os.path.exists(output))
        with open(output, "rb") as f:
            data = f.read()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), "Not a valid PNG")
        self.assertGreater(len(data), 1024, "Screenshot too small")

    def test_emulator_screenshot_has_expected_dimensions(self):
        """Verify screenshot has reasonable dimensions for an Android display."""
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp")
        os.makedirs(undeclared, exist_ok=True)
        output = os.path.join(undeclared, "emulator_dimensions.png")

        _capture_screenshot(output)

        with open(output, "rb") as f:
            data = f.read()

        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        # IHDR starts at byte 16 (8 sig + 4 length + 4 type)
        w, h = struct.unpack(">II", data[16:24])
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)
        print(f"Screenshot dimensions: {w}x{h}")

    def test_golden_comparison(self):
        """Compare live screenshot against committed golden (if exists)."""
        golden_path = os.path.join(GOLDEN_DIR, "emulator_screenshot.png")
        if not os.path.exists(golden_path):
            self.skipTest(f"No golden at {golden_path} — run capture first")

        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR", "/tmp")
        os.makedirs(undeclared, exist_ok=True)
        actual_path = os.path.join(undeclared, "actual_screenshot.png")

        _capture_screenshot(actual_path)

        with open(actual_path, "rb") as f:
            actual = f.read()
        with open(golden_path, "rb") as f:
            golden = f.read()

        self._save_undeclared("actual.png", actual)
        self._save_undeclared("golden.png", golden)

        match, diff_count, diff_png = compare_golden(actual, golden, tolerance=5)
        if diff_png:
            self._save_undeclared("diff.png", diff_png)

        if not match:
            self.fail(
                f"Screenshot does not match golden: {diff_count} pixels differ. "
                f"See diff.png in test outputs."
            )


if __name__ == "__main__":
    unittest.main()
