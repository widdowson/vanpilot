"""Collects and tails log files for emulator instances."""

from __future__ import annotations

import collections
import io
import os
import time
from dataclasses import dataclass
from typing import Iterator, Optional

from instance_manager.src.instance_store import InstanceRecord

_SOURCE_RESCAN_INTERVAL = 5.0


def _clean_dhu_line(text: str) -> str | None:
    """Clean DHU interactive prompt noise, keeping command echoes.

    Returns None for pure-noise lines (just bare prompts like "> " or "> > ").
    For lines with real content after the prompt, returns the text as-is so the
    log reads like a terminal transcript:

        Phone reported protocol version 1.7
        > keycode home
        > tap 300 430
        Video focus gained

    The DHU echoes "> " for every pipe write. A bare "> " is noise, but
    "> keycode home" is a useful command echo we want to keep.
    """
    stripped = text.strip()
    # Pure noise: empty, bare ">", or sequences of "> " with nothing after
    cleaned = stripped
    while cleaned.startswith("> "):
        cleaned = cleaned[2:]
    if cleaned == ">" or cleaned == "":
        return None
    # Has real content — return the original (preserving "> " prefix for commands)
    return stripped


@dataclass
class LogEntry:
    """A single log line with its source."""

    source: str  # "dhu", "emulator", or "service"
    text: str


class LogCollector:
    """Reads and tails log files for a given instance."""

    def __init__(self, service_log_path: Optional[str] = None) -> None:
        self._service_log_path = service_log_path

    def get_sources(self, record: InstanceRecord) -> dict[str, str]:
        """Return {source_name: file_path} for available log sources."""
        sources: dict[str, str] = {}
        if record.log_path and os.path.exists(record.log_path):
            sources["dhu"] = record.log_path
        emu_path = f"/tmp/emu_{record.name}.log"
        if os.path.exists(emu_path):
            sources["emulator"] = emu_path
        if self._service_log_path and os.path.exists(self._service_log_path):
            sources["service"] = self._service_log_path
        return sources

    def read_recent(
        self,
        record: InstanceRecord,
        max_lines_per_source: int = 200,
        sources: Optional[set[str]] = None,
    ) -> list[LogEntry]:
        """Read recent log lines from all (or filtered) sources."""
        available = self.get_sources(record)
        entries: list[LogEntry] = []
        for source_name, path in available.items():
            if sources and source_name not in sources:
                continue
            try:
                with open(path, "r", errors="replace") as f:
                    tail = collections.deque(f, maxlen=max_lines_per_source)
                for line in tail:
                    text = line.rstrip("\n")
                    if source_name == "dhu":
                        text = _clean_dhu_line(text)
                        if text is None:
                            continue
                    entries.append(
                        LogEntry(source=source_name, text=text)
                    )
            except OSError:
                pass
        return entries

    def tail(
        self,
        record: InstanceRecord,
        sources: Optional[set[str]] = None,
        poll_interval: float = 0.5,
    ) -> Iterator[Optional[LogEntry]]:
        """Yield new log lines as they appear, or None on idle polls."""
        available = self.get_sources(record)
        positions: dict[str, tuple[str, io.TextIOWrapper]] = {}
        for source_name, path in available.items():
            if sources and source_name not in sources:
                continue
            try:
                fh = open(path, "r", errors="replace")
                fh.seek(0, 2)  # Seek to end
                positions[source_name] = (path, fh)
            except OSError:
                pass

        last_rescan = time.monotonic()
        try:
            while True:
                found_any = False
                for source_name, (path, fh) in list(positions.items()):
                    # Detect file truncation/rotation
                    try:
                        file_size = os.path.getsize(path)
                        if fh.tell() > file_size:
                            fh.seek(0)
                    except OSError:
                        pass
                    for line in fh:
                        text = line.rstrip("\n")
                        if source_name == "dhu":
                            text = _clean_dhu_line(text)
                            if text is None:
                                continue
                        found_any = True
                        yield LogEntry(
                            source=source_name, text=text
                        )
                if not found_any:
                    yield None
                    time.sleep(poll_interval)

                # Periodically re-scan for new sources
                now = time.monotonic()
                if now - last_rescan >= _SOURCE_RESCAN_INTERVAL:
                    last_rescan = now
                    current_sources = self.get_sources(record)
                    for src_name, src_path in current_sources.items():
                        if sources and src_name not in sources:
                            continue
                        if src_name not in positions:
                            try:
                                fh = open(src_path, "r", errors="replace")
                                fh.seek(0, 2)
                                positions[src_name] = (src_path, fh)
                            except OSError:
                                pass
        finally:
            for _, (_, fh) in positions.items():
                fh.close()
