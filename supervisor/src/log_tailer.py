"""Tails Claude Code JSONL conversation logs and emits TextMessage events.

The supervisor has no other mechanism to surface agent text output to the
Android app. This component watches the JSONL log directory, parses new
assistant messages, and adds them to the EventStore as TextMessage events
so the Android app receives them via GetEvents.

Claude Code JSONL log format (one JSON object per line):
  {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "..."}]}}
  {"type": "human", "message": {"role": "user", "content": [...]}}
  {"type": "system", ...}

Only assistant messages with text content produce TextMessage events.
"""

from __future__ import annotations

import glob
import json
import os
import threading
import time
from typing import Callable, Optional

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore


def parse_log_entry(line: str) -> Optional[dict]:
    """Parse a single JSONL log line and extract assistant text.

    Returns a dict with key "text" if the entry is an assistant message
    containing text content, or None otherwise.
    """
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    if entry.get("type") != "assistant":
        return None

    message = entry.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if content is None:
        return None

    # Content can be a plain string or a list of content blocks
    if isinstance(content, str):
        return {"text": content} if content else None

    if not isinstance(content, list):
        return None

    text_parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text:
                text_parts.append(text)

    if not text_parts:
        return None

    return {"text": " ".join(text_parts)}


def _current_time_ms() -> int:
    return int(time.time() * 1000)


class LogTailer:
    """Watches JSONL log files and emits TextMessage events.

    Each .jsonl file in log_dir corresponds to an agent session.
    The filename stem (without .jsonl) is used as the agent_id.

    Call poll_once() to check for new log entries, or start()/stop()
    to run a background polling thread.
    """

    def __init__(
        self,
        event_store: EventStore,
        log_dir: str = "/tmp/vanpilot/logs",
        poll_interval_s: float = 1.0,
        time_fn: Callable[[], int] = _current_time_ms,
    ) -> None:
        self._event_store = event_store
        self._log_dir = log_dir
        self._poll_interval = poll_interval_s
        self._time_fn = time_fn
        # Track file read offsets: path -> byte offset
        self._offsets: dict[str, int] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def poll_once(self) -> None:
        """Scan all .jsonl files in log_dir for new entries."""
        pattern = os.path.join(self._log_dir, "*.jsonl")
        for path in glob.glob(pattern):
            self._tail_file(path)

    def _tail_file(self, path: str) -> None:
        """Read new lines from a single log file and emit events."""
        agent_id = os.path.splitext(os.path.basename(path))[0]
        offset = self._offsets.get(path, 0)

        try:
            file_size = os.path.getsize(path)
        except OSError:
            return

        # Handle log rotation: if file is smaller than our offset, reset
        if file_size < offset:
            offset = 0

        if file_size == offset:
            return  # No new data

        try:
            with open(path, "r") as f:
                f.seek(offset)
                new_data = f.read()
                new_offset = f.tell()
        except OSError:
            return

        self._offsets[path] = new_offset

        for line in new_data.splitlines():
            parsed = parse_log_entry(line)
            if parsed is not None:
                event = sync_pb2.Event(
                    timestamp_ms=self._time_fn(),
                    text_message=sync_pb2.TextMessage(
                        agent_id=agent_id,
                        content=parsed["text"],
                    ),
                )
                self._event_store.add_event(event)

    def start(self) -> None:
        """Start a background thread that polls for new log entries."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        """Background loop: poll until stopped."""
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(timeout=self._poll_interval)
