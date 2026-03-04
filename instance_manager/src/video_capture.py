"""DHU video capture via screenshot polling.

Captures DHU screenshots at a configurable frame rate and stitches them
into an MP4 video using ffmpeg. Each instance can have at most one active
capture session.

The capture uses the existing DHU screenshot pipe mechanism: each frame
sends a ``screenshot /tmp/path.png`` command to the DHU named pipe,
polls for the file, reads the PNG bytes, then deletes it.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_MAX_FPS = 5
_DEFAULT_FPS = 2
_DEFAULT_MAX_DURATION = 30
_SCREENSHOT_TIMEOUT = 3.0
_SCREENSHOT_POLL_INTERVAL = 0.1


@dataclass
class CaptureSession:
    """State for an active video capture session."""

    capture_id: str
    instance_name: str
    target_fps: int
    max_duration_s: int
    frame_dir: str
    frame_count: int = 0
    actual_fps: float = 0.0
    started_at: float = 0.0
    stopped_at: float = 0.0
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None


class VideoCaptureManager:
    """Manages DHU video capture sessions.

    Each instance can have at most one active capture at a time.
    Frames are captured by sending DHU screenshot commands via the named
    pipe, then stitched into MP4 with ffmpeg on stop.
    """

    def __init__(self, screenshot_fn=None):
        """Initialize the manager.

        Args:
            screenshot_fn: Callable(name, pipe_path, output_path) -> bool
                that sends a screenshot command and returns True if a frame
                was successfully written to output_path. If None, uses the
                default DHU pipe implementation.
        """
        self._screenshot_fn = screenshot_fn or _default_screenshot
        self._sessions: dict[str, CaptureSession] = {}
        self._lock = threading.Lock()

    def start(
        self,
        instance_name: str,
        pipe_path: str,
        target_fps: int = _DEFAULT_FPS,
        max_duration_s: int = _DEFAULT_MAX_DURATION,
    ) -> str:
        """Start capturing video for an instance.

        Args:
            instance_name: Instance to capture.
            pipe_path: Path to DHU named pipe.
            target_fps: Target frames per second (clamped to 1-5).
            max_duration_s: Auto-stop after this many seconds.

        Returns:
            Capture ID string.

        Raises:
            RuntimeError: If a capture is already in progress for this instance.
        """
        target_fps = max(1, min(target_fps or _DEFAULT_FPS, _MAX_FPS))
        max_duration_s = max_duration_s or _DEFAULT_MAX_DURATION

        with self._lock:
            if instance_name in self._sessions:
                raise RuntimeError(
                    f"Capture already in progress for '{instance_name}'"
                )

            capture_id = uuid.uuid4().hex[:12]
            frame_dir = tempfile.mkdtemp(prefix=f"vanpilot_video_{instance_name}_")

            session = CaptureSession(
                capture_id=capture_id,
                instance_name=instance_name,
                target_fps=target_fps,
                max_duration_s=max_duration_s,
                frame_dir=frame_dir,
            )
            self._sessions[instance_name] = session

        thread = threading.Thread(
            target=self._capture_loop,
            args=(session, pipe_path),
            daemon=True,
            name=f"video-capture-{instance_name}",
        )
        session._thread = thread
        session.started_at = time.monotonic()
        thread.start()

        return capture_id

    def stop(self, instance_name: str) -> CaptureResult | None:
        """Stop capturing and stitch frames into MP4.

        Returns:
            CaptureResult with video bytes and metadata, or None if
            no capture was in progress.
        """
        with self._lock:
            session = self._sessions.pop(instance_name, None)

        if session is None:
            return None

        session._stop_event.set()
        if session._thread and session._thread.is_alive():
            session._thread.join(timeout=10)

        session.stopped_at = time.monotonic()
        duration_s = session.stopped_at - session.started_at
        if duration_s > 0 and session.frame_count > 0:
            session.actual_fps = session.frame_count / duration_s

        if session.frame_count == 0:
            self._cleanup_frame_dir(session.frame_dir)
            return CaptureResult(
                capture_id=session.capture_id,
                video_mp4=b"",
                frame_count=0,
                actual_fps=0.0,
                duration_ms=int(duration_s * 1000),
            )

        video_bytes = self._stitch_frames(session)
        self._cleanup_frame_dir(session.frame_dir)

        return CaptureResult(
            capture_id=session.capture_id,
            video_mp4=video_bytes,
            frame_count=session.frame_count,
            actual_fps=round(session.actual_fps, 2),
            duration_ms=int(duration_s * 1000),
        )

    def is_capturing(self, instance_name: str) -> bool:
        """Check if a capture is in progress for the given instance."""
        with self._lock:
            return instance_name in self._sessions

    def active_capture_id(self, instance_name: str) -> str | None:
        """Return the capture ID for an active session, or None."""
        with self._lock:
            session = self._sessions.get(instance_name)
            return session.capture_id if session else None

    def _capture_loop(self, session: CaptureSession, pipe_path: str) -> None:
        """Background thread: capture screenshots at target FPS."""
        interval = 1.0 / session.target_fps
        deadline = time.monotonic() + session.max_duration_s

        while not session._stop_event.is_set():
            if time.monotonic() >= deadline:
                break

            frame_start = time.monotonic()
            frame_path = os.path.join(
                session.frame_dir,
                f"frame_{session.frame_count:06d}.png",
            )

            try:
                ok = self._screenshot_fn(
                    session.instance_name, pipe_path, frame_path
                )
                if ok:
                    session.frame_count += 1
            except Exception:
                log.warning(
                    "Frame capture failed for %s", session.instance_name,
                    exc_info=True,
                )

            elapsed = time.monotonic() - frame_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                session._stop_event.wait(sleep_time)

    def _stitch_frames(self, session: CaptureSession) -> bytes:
        """Use ffmpeg to stitch captured frames into MP4."""
        output_path = os.path.join(session.frame_dir, "output.mp4")
        fps = max(1, round(session.actual_fps)) if session.actual_fps > 0 else session.target_fps

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(fps),
            "-i", os.path.join(session.frame_dir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError) as e:
            log.error("ffmpeg stitch failed: %s", e)
            return b""

        try:
            with open(output_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            return b""

    def _cleanup_frame_dir(self, frame_dir: str) -> None:
        """Remove the temporary frame directory."""
        try:
            shutil.rmtree(frame_dir, ignore_errors=True)
        except Exception:
            pass


@dataclass
class CaptureResult:
    """Result of a completed video capture session."""

    capture_id: str
    video_mp4: bytes
    frame_count: int
    actual_fps: float
    duration_ms: int


def _default_screenshot(name: str, pipe_path: str, output_path: str) -> bool:
    """Default screenshot function using DHU pipe.

    Sends a screenshot command to the DHU named pipe and polls for the
    output file. Returns True if the screenshot was captured.
    """
    # Remove any stale file
    try:
        os.unlink(output_path)
    except FileNotFoundError:
        pass

    # Send screenshot command
    try:
        with open(pipe_path, "w") as pipe:
            pipe.write(f"screenshot {output_path}\n")
    except OSError:
        return False

    # Poll for file
    deadline = time.monotonic() + _SCREENSHOT_TIMEOUT
    while time.monotonic() < deadline:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        time.sleep(_SCREENSHOT_POLL_INTERVAL)

    return False
