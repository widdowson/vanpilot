"""Tmux input injection with delivery verification.

Injects user prompts into Claude Code agent tmux sessions via
``tmux send-keys`` and monitors the conversation log for a response.
If no response is detected within a configurable timeout, an
InputDeliveryFailure event is emitted to the EventStore.
"""

from __future__ import annotations

import os
import threading
import time

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore
from supervisor.src.tmux_launcher import TmuxLauncher


class InputInjector:
    """Injects text into tmux sessions and verifies delivery.

    After sending keys, the injector monitors the agent's conversation log
    file for growth.  If the file does not grow within *response_timeout_s*
    seconds, an ``InputDeliveryFailure`` event is added to the store.

    Limitations
    -----------
    Response detection is size-based, not content-based.  Any log file
    growth — including output from other agents, system messages, or
    unrelated writes — is treated as a successful response.  A future
    refinement could parse the JSON log entries and check for a new entry
    whose timestamp falls after the injection time, providing true
    content-based verification.
    """

    def __init__(
        self,
        tmux: TmuxLauncher,
        event_store: EventStore,
        log_dir: str = "/tmp/vanpilot/logs",
        response_timeout_s: float = 30.0,
        poll_interval_s: float = 0.5,
    ) -> None:
        self._tmux = tmux
        self._event_store = event_store
        self._log_dir = log_dir
        self._timeout = response_timeout_s
        self._poll_interval = poll_interval_s

    def _log_path(self, session_name: str) -> str:
        """Derive the conversation log path for a tmux session."""
        return os.path.join(self._log_dir, f"{session_name}.jsonl")

    def _get_log_size(self, path: str) -> int:
        """Return the current size of a log file, or 0 if it doesn't exist."""
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def inject(
        self, session_name: str, text: str, agent_id: str = "lead"
    ) -> bool:
        """Inject *text* into the tmux session and wait for a response.

        Sends keys to the tmux session using ``tmux send-keys -t <session>``.
        Only the session name is used (no ``:<pane>`` suffix) because each
        Claude Code agent runs in a single-pane tmux session, so the
        default active pane is always correct.

        Returns ``True`` if a response was detected within the timeout,
        ``False`` otherwise.  On timeout an ``InputDeliveryFailure`` event
        is emitted to the event store.
        """
        log_file = self._log_path(session_name)
        size_before = self._get_log_size(log_file)

        self._tmux.send_keys(session_name, text)

        if self._wait_for_response(log_file, size_before):
            return True

        self._emit_failure(text, agent_id)
        return False

    def inject_async(
        self, session_name: str, text: str, agent_id: str = "lead"
    ) -> threading.Thread:
        """Fire-and-forget variant of :meth:`inject`.

        Sends keys and monitors for a response in a background daemon
        thread so the caller is not blocked.  Returns the thread handle
        so callers can join if needed.
        """
        thread = threading.Thread(
            target=self.inject,
            args=(session_name, text, agent_id),
            daemon=True,
        )
        thread.start()
        return thread

    def _wait_for_response(self, log_file: str, initial_size: int) -> bool:
        """Poll the log file for growth within the configured timeout."""
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            if self._get_log_size(log_file) > initial_size:
                return True
            time.sleep(self._poll_interval)
        return False

    def _emit_failure(self, text: str, agent_id: str) -> None:
        """Add an InputDeliveryFailure event to the store."""
        event = sync_pb2.Event(
            timestamp_ms=int(time.time() * 1000),
            input_delivery_failure=sync_pb2.InputDeliveryFailure(
                attempted_input=text,
                target_agent_id=agent_id,
            ),
        )
        self._event_store.add_event(event)
