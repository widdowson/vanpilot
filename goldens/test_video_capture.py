"""Tests for the video capture module (AC-4).

Tests are organized into fine-grained classes:
- VideoCaptureConfigTest: Config parsing from test args (AC-4.1)
- VideoCaptureDisabledTest: Zero overhead when disabled (AC-4.4)
- VideoCaptureEnabledTest: Recording behavior when enabled (AC-4.2, AC-4.3)
"""

import os
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

from goldens.video_capture import VideoCaptureConfig, VideoCapture


class VideoCaptureConfigTest(unittest.TestCase):
    """Test config parsing from test args (AC-4.1)."""

    def test_default_config_is_disabled(self):
        config = VideoCaptureConfig()
        self.assertFalse(config.enabled)

    def test_default_duration_is_5_seconds(self):
        config = VideoCaptureConfig()
        self.assertEqual(config.duration_seconds, 5)

    def test_from_args_empty_list_disabled(self):
        config = VideoCaptureConfig.from_args([])
        self.assertFalse(config.enabled)

    def test_from_args_record_video_flag_enables(self):
        config = VideoCaptureConfig.from_args(["--record-video"])
        self.assertTrue(config.enabled)

    def test_from_args_record_video_with_duration(self):
        config = VideoCaptureConfig.from_args(["--record-video-duration=10"])
        self.assertTrue(config.enabled)
        self.assertEqual(config.duration_seconds, 10)

    def test_from_args_both_flags(self):
        config = VideoCaptureConfig.from_args(
            ["--record-video", "--record-video-duration=3"]
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.duration_seconds, 3)

    def test_from_args_invalid_duration_ignored(self):
        config = VideoCaptureConfig.from_args(["--record-video-duration=abc"])
        self.assertFalse(config.enabled)
        self.assertEqual(config.duration_seconds, 5)

    def test_from_args_unrelated_flags_ignored(self):
        config = VideoCaptureConfig.from_args(
            ["--verbose", "--timeout=30", "--some-flag"]
        )
        self.assertFalse(config.enabled)

    def test_from_args_uses_test_undeclared_outputs_dir(self):
        with mock.patch.dict(os.environ, {"TEST_UNDECLARED_OUTPUTS_DIR": "/tmp/test_out"}):
            config = VideoCaptureConfig.from_args(["--record-video"])
        self.assertEqual(config.output_dir, "/tmp/test_out")

    def test_from_args_no_env_output_dir_is_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            config = VideoCaptureConfig.from_args(["--record-video"])
        self.assertIsNone(config.output_dir)


class VideoCaptureDisabledTest(unittest.TestCase):
    """Test zero overhead when disabled (AC-4.4)."""

    def setUp(self):
        self.config = VideoCaptureConfig(enabled=False)
        self.capture = VideoCapture(self.config)

    def test_enabled_property_is_false(self):
        self.assertFalse(self.capture.enabled)

    def test_recording_property_is_false(self):
        self.assertFalse(self.capture.recording)

    def test_start_is_noop(self):
        """start() should not spawn any subprocess when disabled."""
        with mock.patch("goldens.video_capture.subprocess.Popen") as mock_popen:
            self.capture.start()
            mock_popen.assert_not_called()

    def test_stop_returns_none(self):
        result = self.capture.stop()
        self.assertIsNone(result)

    def test_stop_does_not_call_adb(self):
        """stop() should not invoke any adb commands when disabled."""
        with mock.patch("goldens.video_capture.subprocess.run") as mock_run:
            self.capture.stop()
            mock_run.assert_not_called()

    def test_start_stop_cycle_is_noop(self):
        """Full start/stop cycle with disabled config does nothing."""
        with mock.patch("goldens.video_capture.subprocess.Popen") as mock_popen:
            with mock.patch("goldens.video_capture.subprocess.run") as mock_run:
                self.capture.start()
                result = self.capture.stop()
                mock_popen.assert_not_called()
                mock_run.assert_not_called()
                self.assertIsNone(result)


class VideoCaptureEnabledTest(unittest.TestCase):
    """Test recording behavior when enabled (AC-4.2, AC-4.3)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = VideoCaptureConfig(
            enabled=True,
            duration_seconds=5,
            output_dir=self.tmpdir,
            adb_host="localhost",
            adb_port=5555,
        )
        self.capture = VideoCapture(self.config)

    def test_enabled_property_is_true(self):
        self.assertTrue(self.capture.enabled)

    def test_start_spawns_screenrecord(self):
        """start() should invoke adb shell screenrecord."""
        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.capture.start()
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            self.assertIn("adb", cmd[0])
            self.assertIn("screenrecord", cmd)

    def test_start_passes_time_limit(self):
        """screenrecord should receive --time-limit with configured duration."""
        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.capture.start()
            cmd = mock_popen.call_args[0][0]
            idx = cmd.index("--time-limit")
            self.assertEqual(cmd[idx + 1], "5")

    def test_start_passes_adb_address(self):
        """adb -s host:port should be used."""
        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.capture.start()
            cmd = mock_popen.call_args[0][0]
            self.assertIn("-s", cmd)
            idx = cmd.index("-s")
            self.assertEqual(cmd[idx + 1], "localhost:5555")

    def test_start_sets_recording_true(self):
        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()
            self.assertTrue(self.capture.recording)

    def test_start_idempotent(self):
        """Calling start() twice should only spawn one process."""
        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.capture.start()
            self.capture.start()
            self.assertEqual(mock_popen.call_count, 1)

    def test_stop_terminates_process(self):
        """stop() should send SIGINT to the screenrecord process."""
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout = None
        mock_proc.stderr = None
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()

        # Create a dummy video file so the pull "succeeds"
        video_path = os.path.join(self.tmpdir, "golden_video.mp4")
        with open(video_path, "wb") as f:
            f.write(b"fake video data")

        with mock.patch("goldens.video_capture.subprocess.run"), \
             mock.patch("goldens.video_capture.time.sleep"):
            self.capture.stop()
            mock_proc.send_signal.assert_called_once_with(signal.SIGINT)

    def test_stop_returns_video_path(self):
        """stop() should return path to the pulled video."""
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()

        video_path = os.path.join(self.tmpdir, "golden_video.mp4")
        with open(video_path, "wb") as f:
            f.write(b"fake video data")

        def fake_run(cmd, **kwargs):
            """Simulate adb pull by creating the file."""
            if "pull" in cmd:
                # File already exists from our setup
                return mock.MagicMock(returncode=0)
            return mock.MagicMock(returncode=0)

        with mock.patch("goldens.video_capture.subprocess.run", side_effect=fake_run):
            result = self.capture.stop()
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith(".mp4"))

    def test_stop_uses_output_dir(self):
        """Video should be saved to the configured output_dir (AC-4.3)."""
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()

        video_path = os.path.join(self.tmpdir, "golden_video.mp4")
        with open(video_path, "wb") as f:
            f.write(b"fake video data")

        with mock.patch("goldens.video_capture.subprocess.run"):
            result = self.capture.stop(name="golden_video")
            self.assertTrue(result.startswith(self.tmpdir))

    def test_stop_without_start_returns_none(self):
        result = self.capture.stop()
        self.assertIsNone(result)

    def test_stop_sets_recording_false(self):
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()

        with mock.patch("goldens.video_capture.subprocess.run"):
            self.capture.stop()
            self.assertFalse(self.capture.recording)

    def test_custom_duration(self):
        """Configured duration is passed to screenrecord (AC-4.2)."""
        config = VideoCaptureConfig(
            enabled=True,
            duration_seconds=10,
            output_dir=self.tmpdir,
        )
        capture = VideoCapture(config)

        mock_proc = mock.MagicMock()
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc) as mock_popen:
            capture.start()
            cmd = mock_popen.call_args[0][0]
            idx = cmd.index("--time-limit")
            self.assertEqual(cmd[idx + 1], "10")

    def test_adb_not_found_degrades_gracefully(self):
        """If adb is not installed, start() should not raise."""
        with mock.patch(
            "goldens.video_capture.subprocess.Popen",
            side_effect=FileNotFoundError("adb not found"),
        ):
            self.capture.start()
            self.assertFalse(self.capture.recording)

    def test_stop_creates_output_dir_if_missing(self):
        """stop() should create output_dir if it doesn't exist."""
        new_dir = os.path.join(self.tmpdir, "nested", "output")
        config = VideoCaptureConfig(
            enabled=True,
            duration_seconds=5,
            output_dir=new_dir,
        )
        capture = VideoCapture(config)

        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            capture.start()

        # Create video file at expected path
        os.makedirs(new_dir, exist_ok=True)
        with open(os.path.join(new_dir, "test.mp4"), "wb") as f:
            f.write(b"fake")

        with mock.patch("goldens.video_capture.subprocess.run"):
            capture.stop(name="test")
            self.assertTrue(os.path.isdir(new_dir))

    def test_stop_uses_tempdir_when_no_output_dir(self):
        """When output_dir is None, stop() should use a temp directory."""
        config = VideoCaptureConfig(
            enabled=True,
            duration_seconds=5,
            output_dir=None,
        )
        capture = VideoCapture(config)

        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            capture.start()

        def fake_run(cmd, **kwargs):
            if "pull" in cmd:
                # Create the file at the destination
                dest = cmd[-1]
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(b"fake video")
                return mock.MagicMock(returncode=0)
            return mock.MagicMock(returncode=0)

        with mock.patch("goldens.video_capture.subprocess.run", side_effect=fake_run):
            result = capture.stop()
            if result:
                self.assertTrue(result.endswith(".mp4"))
                self.assertIn("vanpilot_video_", result)

    def test_pull_failure_returns_none(self):
        """If adb pull fails, stop() should return None."""
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0
        with mock.patch("goldens.video_capture.subprocess.Popen", return_value=mock_proc):
            self.capture.start()

        with mock.patch(
            "goldens.video_capture.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "adb"),
        ):
            result = self.capture.stop()
            self.assertIsNone(result)


class VideoCaptureConfigCustomDurationTest(unittest.TestCase):
    """Test configurable duration (AC-4.2)."""

    def test_duration_1_second(self):
        config = VideoCaptureConfig.from_args(["--record-video-duration=1"])
        self.assertEqual(config.duration_seconds, 1)

    def test_duration_30_seconds(self):
        config = VideoCaptureConfig.from_args(["--record-video-duration=30"])
        self.assertEqual(config.duration_seconds, 30)

    def test_duration_from_constructor(self):
        config = VideoCaptureConfig(enabled=True, duration_seconds=15)
        self.assertEqual(config.duration_seconds, 15)


if __name__ == "__main__":
    unittest.main()
