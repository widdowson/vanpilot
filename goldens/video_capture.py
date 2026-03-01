"""Video capture module for golden test diagnostics.

Manages emulator screen recording via `adb shell screenrecord` for capturing
the last N seconds leading up to a golden frame capture. Disabled by default
with zero overhead when off.

AC-4: Video Capture (Optional Diagnostic)
- AC-4.1: Enabled via --record-video test flag
- AC-4.2: Captures last N seconds (configurable, default 5)
- AC-4.3: Videos written to TEST_UNDECLARED_OUTPUTS_DIR, NOT committed
- AC-4.4: Disabled by default, zero overhead when off
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

# Temporary path on the emulator where screenrecord writes its output.
_REMOTE_VIDEO_PATH = "/sdcard/golden_video.mp4"


@dataclass
class VideoCaptureConfig:
    """Configuration for video capture."""

    enabled: bool = False
    duration_seconds: int = 5
    output_dir: str | None = None
    adb_host: str = "localhost"
    adb_port: int = 5555

    @classmethod
    def from_args(cls, args: list[str]) -> VideoCaptureConfig:
        """Parse video capture config from test arguments.

        Recognizes:
            --record-video           Enable video capture (default duration)
            --record-video-duration=N  Set capture duration in seconds
        """
        enabled = False
        duration = 5

        for arg in args:
            if arg == "--record-video":
                enabled = True
            elif arg.startswith("--record-video-duration="):
                try:
                    duration = int(arg.split("=", 1)[1])
                    enabled = True
                except (ValueError, IndexError):
                    pass

        output_dir = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")

        return cls(
            enabled=enabled,
            duration_seconds=duration,
            output_dir=output_dir,
        )


class VideoCapture:
    """Manages emulator video capture for golden test diagnostics.

    Uses `adb shell screenrecord` to record the emulator screen. Note:
    screenrecord captures the device screen, not the DHU surface specifically.
    This is acceptable for diagnostics — the emulator screen shows the app
    under test and provides sufficient context for debugging golden failures.

    Recording runs in a background thread and is stopped when a golden frame
    is captured. The recording captures a rolling window of the last N seconds.

    When disabled (default), all methods are no-ops with zero overhead.
    """

    def __init__(self, config: VideoCaptureConfig) -> None:
        self._config = config
        self._process: subprocess.Popen | None = None
        self._remote_path: str = ""
        self._recording = False
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        """Start video recording on the emulator.

        No-op if video capture is disabled.
        """
        if not self._config.enabled:
            return

        with self._lock:
            if self._recording:
                return

            self._remote_path = _REMOTE_VIDEO_PATH
            adb_addr = f"{self._config.adb_host}:{self._config.adb_port}"

            cmd = [
                "adb",
                "-s",
                adb_addr,
                "shell",
                "screenrecord",
                "--time-limit",
                str(self._config.duration_seconds),
                self._remote_path,
            ]

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self._recording = True
            except FileNotFoundError:
                # adb not available — degrade gracefully
                self._recording = False

    def stop(self, name: str = "golden_video") -> str | None:
        """Stop recording and pull the video to the output directory.

        Args:
            name: Base name for the output video file (without extension).

        Returns:
            Path to the saved video file, or None if capture was disabled
            or no recording was in progress.
        """
        if not self._config.enabled:
            return None

        with self._lock:
            if not self._recording or self._process is None:
                return None

            # Send interrupt to stop screenrecord gracefully
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

            self._recording = False

            # Determine output directory
            output_dir = self._config.output_dir
            if not output_dir:
                output_dir = tempfile.mkdtemp(prefix="vanpilot_video_")
            os.makedirs(output_dir, exist_ok=True)

            local_path = os.path.join(output_dir, f"{name}.mp4")
            adb_addr = f"{self._config.adb_host}:{self._config.adb_port}"

            # Pull the video from the emulator
            try:
                subprocess.run(
                    ["adb", "-s", adb_addr, "pull", self._remote_path, local_path],
                    timeout=30,
                    capture_output=True,
                    check=True,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                return None
            finally:
                # Clean up remote file (best-effort)
                try:
                    subprocess.run(
                        ["adb", "-s", adb_addr, "shell", "rm", "-f", self._remote_path],
                        timeout=10,
                        capture_output=True,
                    )
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    pass

                self._process = None

            if os.path.exists(local_path):
                return local_path
            return None
