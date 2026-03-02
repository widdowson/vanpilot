"""Watchdog monitoring for agent tmux sessions.

Monitors each registered tmux session for output activity. If a session
produces no new output within a configurable timeout, a WatchdogTimeout
event is emitted into the EventStore.
"""

import subprocess
import threading
import time
from typing import Callable, Dict, Optional

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore


def _default_capture_pane(session_name: str) -> str:
    """Capture the current content of a tmux pane.

    Uses ``tmux capture-pane -p`` to dump the pane contents as text.
    """
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", session_name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to capture pane for '{session_name}': {result.stderr}"
        )
    return result.stdout


class _SessionState:
    """Tracks the last known output and activity time for a session."""

    __slots__ = ("session_name", "last_output", "last_activity_time")

    def __init__(self, session_name: str, now: float) -> None:
        self.session_name = session_name
        self.last_output: Optional[str] = None
        self.last_activity_time: float = now


class Watchdog:
    """Monitors tmux sessions and emits WatchdogTimeout events for silent agents."""

    def __init__(
        self,
        event_store: EventStore,
        timeout_seconds: float = 60.0,
        check_interval_seconds: float = 5.0,
        capture_pane_fn: Optional[Callable[[str], str]] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._event_store = event_store
        self._timeout_seconds = timeout_seconds
        self._check_interval = check_interval_seconds
        self._capture_pane = capture_pane_fn or _default_capture_pane
        self._clock = clock or time.monotonic
        self._sessions: Dict[str, _SessionState] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def monitored_agents(self) -> list:
        """Return a list of currently monitored agent IDs."""
        with self._lock:
            return list(self._sessions.keys())

    @property
    def is_running(self) -> bool:
        """Whether the background monitoring thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def register_session(self, agent_id: str, session_name: str) -> None:
        """Start monitoring a tmux session for the given agent."""
        with self._lock:
            self._sessions[agent_id] = _SessionState(session_name, self._clock())

    def unregister_session(self, agent_id: str) -> None:
        """Stop monitoring the given agent's session."""
        with self._lock:
            self._sessions.pop(agent_id, None)

    def check_sessions(self) -> None:
        """Run a single check cycle across all registered sessions.

        For each session, captures the current pane output and compares it
        to the last known output. If the output has changed, the activity
        timer is reset. If it hasn't changed and the timeout has been
        exceeded, a WatchdogTimeout event is emitted.
        """
        with self._lock:
            sessions_snapshot = dict(self._sessions)

        now = self._clock()

        for agent_id, state in sessions_snapshot.items():
            try:
                current_output = self._capture_pane(state.session_name)
            except Exception:
                # If we can't capture the pane (session gone, tmux error),
                # skip this cycle rather than crashing the watchdog.
                continue

            if state.last_output is None or current_output != state.last_output:
                # Output changed (or first check) — reset timer
                state.last_output = current_output
                state.last_activity_time = now
            else:
                # Output unchanged — check if timeout exceeded
                silent_seconds = now - state.last_activity_time
                if silent_seconds >= self._timeout_seconds:
                    silent_ms = int(silent_seconds * 1000)
                    event = sync_pb2.Event(
                        timestamp_ms=int(time.time() * 1000),
                        watchdog_timeout=sync_pb2.WatchdogTimeout(
                            agent_id=agent_id,
                            silent_duration_ms=silent_ms,
                        ),
                    )
                    self._event_store.add_event(event)
                    # Reset timer to avoid flooding events every check cycle
                    state.last_activity_time = now

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="watchdog", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run_loop(self) -> None:
        """Background loop that periodically checks sessions."""
        while not self._stop_event.is_set():
            self.check_sessions()
            self._stop_event.wait(timeout=self._check_interval)
