"""Tests for the DHU video capture module."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from instance_manager.src.video_capture import (
    CaptureResult,
    CaptureSession,
    VideoCaptureManager,
)


class FakeScreenshot:
    """Controllable fake screenshot function for tests."""

    def __init__(self, delay: float = 0.01, fail: bool = False):
        self.delay = delay
        self.fail = fail
        self.call_count = 0
        self._lock = threading.Lock()

    def __call__(self, name: str, pipe_path: str, output_path: str) -> bool:
        with self._lock:
            self.call_count += 1
        time.sleep(self.delay)
        if self.fail:
            return False
        # Write a minimal fake PNG header
        with open(output_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        return True


class TestVideoCaptureManagerStart(unittest.TestCase):
    """Tests for starting video capture sessions."""

    def test_start_returns_capture_id(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        capture_id = mgr.start("test-instance", "/tmp/fake_pipe")
        self.assertIsInstance(capture_id, str)
        self.assertEqual(len(capture_id), 12)
        # Clean up
        mgr.stop("test-instance")

    def test_start_sets_capturing_state(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        mgr.start("test-instance", "/tmp/fake_pipe")
        self.assertTrue(mgr.is_capturing("test-instance"))
        mgr.stop("test-instance")

    def test_start_duplicate_raises(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        mgr.start("test-instance", "/tmp/fake_pipe")
        with self.assertRaises(RuntimeError):
            mgr.start("test-instance", "/tmp/fake_pipe")
        mgr.stop("test-instance")

    def test_start_clamps_fps_min(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe", target_fps=0)
        # 0 means "use default" (2), not "clamp to 1"
        with mgr._lock:
            session = mgr._sessions["test-instance"]
        self.assertEqual(session.target_fps, 2)
        mgr.stop("test-instance")

    def test_start_clamps_fps_max(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe", target_fps=100)
        with mgr._lock:
            session = mgr._sessions["test-instance"]
        self.assertEqual(session.target_fps, 5)
        mgr.stop("test-instance")

    def test_active_capture_id(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        capture_id = mgr.start("test-instance", "/tmp/fake_pipe")
        self.assertEqual(mgr.active_capture_id("test-instance"), capture_id)
        mgr.stop("test-instance")

    def test_active_capture_id_none_when_not_capturing(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        self.assertIsNone(mgr.active_capture_id("test-instance"))


class TestVideoCaptureManagerStop(unittest.TestCase):
    """Tests for stopping video capture sessions."""

    def test_stop_returns_none_when_not_capturing(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        result = mgr.stop("nonexistent")
        self.assertIsNone(result)

    def test_stop_clears_capturing_state(self):
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        mgr.start("test-instance", "/tmp/fake_pipe")
        mgr.stop("test-instance")
        self.assertFalse(mgr.is_capturing("test-instance"))

    def test_stop_returns_capture_result(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        capture_id = mgr.start("test-instance", "/tmp/fake_pipe", target_fps=5)
        # Let it capture a few frames
        time.sleep(0.2)
        result = mgr.stop("test-instance")

        self.assertIsInstance(result, CaptureResult)
        self.assertEqual(result.capture_id, capture_id)
        self.assertGreater(result.frame_count, 0)
        self.assertGreater(result.duration_ms, 0)

    def test_stop_cleans_up_frame_dir(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe")
        time.sleep(0.1)

        # Peek at the frame dir before stopping
        with mgr._lock:
            frame_dir = mgr._sessions["test-instance"].frame_dir
        self.assertTrue(os.path.isdir(frame_dir))

        mgr.stop("test-instance")
        self.assertFalse(os.path.exists(frame_dir))

    def test_stop_with_zero_frames(self):
        fake = FakeScreenshot(fail=True)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe")
        time.sleep(0.1)
        result = mgr.stop("test-instance")

        self.assertIsInstance(result, CaptureResult)
        self.assertEqual(result.frame_count, 0)
        self.assertEqual(result.video_mp4, b"")

    def test_can_restart_after_stop(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe")
        mgr.stop("test-instance")
        # Should be able to start again
        capture_id = mgr.start("test-instance", "/tmp/fake_pipe")
        self.assertIsInstance(capture_id, str)
        mgr.stop("test-instance")


class TestVideoCaptureManagerAutoStop(unittest.TestCase):
    """Tests for auto-stop via max_duration_s."""

    def test_auto_stop_after_max_duration(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe", max_duration_s=1)

        # Wait for auto-stop
        time.sleep(1.5)

        # The capture loop should have exited, but the session is still
        # tracked until stop() is called
        self.assertTrue(mgr.is_capturing("test-instance"))

        result = mgr.stop("test-instance")
        self.assertIsInstance(result, CaptureResult)
        self.assertGreater(result.frame_count, 0)


class TestVideoCaptureManagerMultipleInstances(unittest.TestCase):
    """Tests for concurrent captures on different instances."""

    def test_independent_captures(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)

        id1 = mgr.start("instance-a", "/tmp/pipe_a")
        id2 = mgr.start("instance-b", "/tmp/pipe_b")

        self.assertNotEqual(id1, id2)
        self.assertTrue(mgr.is_capturing("instance-a"))
        self.assertTrue(mgr.is_capturing("instance-b"))

        time.sleep(0.1)

        result_a = mgr.stop("instance-a")
        self.assertTrue(mgr.is_capturing("instance-b"))

        result_b = mgr.stop("instance-b")
        self.assertFalse(mgr.is_capturing("instance-a"))
        self.assertFalse(mgr.is_capturing("instance-b"))

        self.assertIsInstance(result_a, CaptureResult)
        self.assertIsInstance(result_b, CaptureResult)


class TestStitchFrames(unittest.TestCase):
    """Tests for ffmpeg stitching."""

    @patch("instance_manager.src.video_capture.subprocess.run")
    def test_stitch_calls_ffmpeg(self, mock_run):
        """Verify ffmpeg is called with correct arguments."""
        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())

        frame_dir = tempfile.mkdtemp()
        # Create fake frame files
        for i in range(3):
            path = os.path.join(frame_dir, f"frame_{i:06d}.png")
            with open(path, "wb") as f:
                f.write(b"\x89PNG" + b"\x00" * 100)

        # Write a fake output file so _stitch_frames can read it
        output_path = os.path.join(frame_dir, "output.mp4")
        with open(output_path, "wb") as f:
            f.write(b"fake-mp4-data")

        session = CaptureSession(
            capture_id="test123",
            instance_name="test",
            target_fps=2,
            max_duration_s=30,
            frame_dir=frame_dir,
            frame_count=3,
            actual_fps=2.0,
        )

        result = mgr._stitch_frames(session)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-framerate", cmd)
        self.assertIn("2", cmd)
        self.assertEqual(result, b"fake-mp4-data")

        # Clean up
        import shutil
        shutil.rmtree(frame_dir, ignore_errors=True)

    @patch("instance_manager.src.video_capture.subprocess.run")
    def test_stitch_returns_empty_on_ffmpeg_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")

        mgr = VideoCaptureManager(screenshot_fn=FakeScreenshot())
        frame_dir = tempfile.mkdtemp()

        session = CaptureSession(
            capture_id="test123",
            instance_name="test",
            target_fps=2,
            max_duration_s=30,
            frame_dir=frame_dir,
            frame_count=3,
            actual_fps=2.0,
        )

        result = mgr._stitch_frames(session)
        self.assertEqual(result, b"")

        import shutil
        shutil.rmtree(frame_dir, ignore_errors=True)


class TestCaptureFrameCount(unittest.TestCase):
    """Tests verifying frame counting behavior."""

    def test_frame_count_increments(self):
        fake = FakeScreenshot(delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe", target_fps=5)
        time.sleep(0.3)
        result = mgr.stop("test-instance")
        # At 5 FPS with 0.01s capture time, ~0.3s should yield a few frames
        self.assertGreater(result.frame_count, 0)
        self.assertGreater(fake.call_count, 0)

    def test_failed_frames_not_counted(self):
        fake = FakeScreenshot(fail=True, delay=0.01)
        mgr = VideoCaptureManager(screenshot_fn=fake)
        mgr.start("test-instance", "/tmp/fake_pipe", target_fps=5)
        time.sleep(0.2)
        result = mgr.stop("test-instance")
        # Screenshot function returns False, frames shouldn't be counted
        self.assertEqual(result.frame_count, 0)
        self.assertGreater(fake.call_count, 0)


if __name__ == "__main__":
    unittest.main()
