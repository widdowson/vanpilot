"""Golden tests using the instance manager for automated emulator lifecycle.

These tests connect to a running InstanceManagerService to create
emulator+DHU pairs, capture screenshots, and compare against committed
goldens in goldens/phase9/.

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to VanPilot APK (optional — skips install if unset)
  GOLDEN_TOLERANCE: Per-channel pixel tolerance (default 5)

Usage:
  # Start the instance manager first, then:
  bazel test //goldens:instance_golden_dhu_test \
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061 \
    --test_env=VANPILOT_APK=bazel-bin/android/vanpilot.apk

  # Or without APK install (emulator already has app installed via snapshot):
  bazel test //goldens:instance_golden_dhu_test \
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061
"""

import os
import struct
import unittest

from goldens.golden_test_harness import GoldenTestCase


GOLDEN_DIR = os.path.join(
    os.environ.get("TEST_SRCDIR", ""),
    os.environ.get("TEST_WORKSPACE", ""),
    "goldens",
    "phase9",
)


class DHUScreenshotGoldenTest(GoldenTestCase):
    """Compare DHU screenshots from the instance manager against goldens."""

    instance_name = "golden-dhu"

    def test_dhu_screenshot_is_valid_png(self):
        """Verify the DHU screenshot is a valid PNG."""
        png = self.capture_dhu_screenshot()
        self.assertTrue(
            png.startswith(b"\x89PNG\r\n\x1a\n"),
            "DHU screenshot is not a valid PNG",
        )
        self.assertGreater(len(png), 1024, "DHU screenshot too small")
        self.save_test_output("dhu_capture.png", png)

    def test_dhu_screenshot_has_reasonable_dimensions(self):
        """Verify the DHU screenshot has non-zero dimensions."""
        png = self.capture_dhu_screenshot()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h = struct.unpack(">II", png[16:24])
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_dhu_golden_comparison(self):
        """Compare DHU screenshot against committed golden."""
        golden_path = os.path.join(GOLDEN_DIR, "dhu_screenshot.png")
        png = self.capture_dhu_screenshot()
        self.assert_matches_golden(png, golden_path)


class EmulatorScreenshotGoldenTest(GoldenTestCase):
    """Compare emulator screenshots (adb screencap) against goldens."""

    instance_name = "golden-emu"

    def test_emulator_screenshot_is_valid_png(self):
        """Verify adb screencap returns a valid PNG."""
        png = self.capture_emulator_screenshot()
        self.assertTrue(
            png.startswith(b"\x89PNG\r\n\x1a\n"),
            "Emulator screenshot is not a valid PNG",
        )
        self.assertGreater(len(png), 1024, "Emulator screenshot too small")
        self.save_test_output("emulator_capture.png", png)

    def test_emulator_screenshot_has_expected_dimensions(self):
        """Verify emulator screenshot has reasonable dimensions."""
        png = self.capture_emulator_screenshot()
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h = struct.unpack(">II", png[16:24])
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_emulator_golden_comparison(self):
        """Compare emulator screenshot against committed golden."""
        golden_path = os.path.join(GOLDEN_DIR, "emulator_screenshot.png")
        png = self.capture_emulator_screenshot()
        self.assert_matches_golden(png, golden_path)


if __name__ == "__main__":
    unittest.main()
