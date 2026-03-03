"""Tests for video capture wiring in emulator golden test (AC-4.2).

Verifies that the emulator golden test module integrates video_capture
for recording the emulator screen during test runs. When --record-video
is passed as a test arg, video should be captured during the test lifecycle.
"""

import sys
import unittest
from unittest import mock

from goldens.video_capture import VideoCaptureConfig, VideoCapture


class EmulatorGoldenVideoWiringTest(unittest.TestCase):
    """Verify video capture is wired into emulator golden test."""

    def _load_module(self, extra_argv=None):
        """Load test_emulator_golden with mocked subprocess and controlled argv."""
        test_argv = ["test_emulator_golden"]
        if extra_argv:
            test_argv.extend(extra_argv)

        # Clear cached module to force re-evaluation of module-level code.
        # Must also clear the attribute from the parent package, otherwise
        # Python reuses the stale reference from the previous import.
        mods_to_remove = [k for k in sys.modules if "test_emulator_golden" in k]
        for k in mods_to_remove:
            del sys.modules[k]
        goldens_pkg = sys.modules.get("goldens")
        if goldens_pkg and hasattr(goldens_pkg, "test_emulator_golden"):
            delattr(goldens_pkg, "test_emulator_golden")

        with (
            mock.patch.object(sys, "argv", test_argv),
            mock.patch(
                "subprocess.run",
                return_value=mock.Mock(stdout="", returncode=0),
            ),
            mock.patch("subprocess.Popen"),
        ):
            from goldens import test_emulator_golden as mod

            return mod

    def test_exports_video_config(self):
        """Module must export VIDEO_CONFIG as a VideoCaptureConfig."""
        mod = self._load_module()
        self.assertIsInstance(mod.VIDEO_CONFIG, VideoCaptureConfig)

    def test_exports_video_capture(self):
        """Module must export VIDEO_CAPTURE as a VideoCapture instance."""
        mod = self._load_module()
        self.assertIsInstance(mod.VIDEO_CAPTURE, VideoCapture)

    def test_video_disabled_by_default(self):
        """Without --record-video, VIDEO_CONFIG.enabled must be False."""
        mod = self._load_module()
        self.assertFalse(mod.VIDEO_CONFIG.enabled)

    def test_video_enabled_with_record_flag(self):
        """With --record-video, VIDEO_CONFIG.enabled must be True."""
        mod = self._load_module(extra_argv=["--record-video"])
        self.assertTrue(mod.VIDEO_CONFIG.enabled)

    def test_setup_class_starts_video(self):
        """EmulatorGoldenTest.setUpClass must call VIDEO_CAPTURE.start()."""
        mod = self._load_module(extra_argv=["--record-video"])
        with mock.patch.object(mod.VIDEO_CAPTURE, "start") as mock_start:
            mod.EmulatorGoldenTest.setUpClass()
            mock_start.assert_called_once()

    def test_teardown_class_stops_video(self):
        """EmulatorGoldenTest.tearDownClass must call VIDEO_CAPTURE.stop()."""
        mod = self._load_module(extra_argv=["--record-video"])
        with mock.patch.object(mod.VIDEO_CAPTURE, "stop") as mock_stop:
            mod.EmulatorGoldenTest.tearDownClass()
            mock_stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
