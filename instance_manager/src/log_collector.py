"""Collects and tails log files for emulator instances."""

from __future__ import annotations

import collections
import io
import os
import time
from dataclasses import dataclass
from typing import Iterator

from instance_manager.src.instance_store import InstanceRecord, InstanceStore

_SOURCE_RESCAN_INTERVAL = 5.0

# DHU logs contain prompt noise lines (bare "> " prompts) that get filtered
# out by _clean_dhu_line.  Over-read by this factor so the final displayed
# count is closer to max_lines_per_source after filtering.
_DHU_OVERREAD_FACTOR = 2


def _clean_dhu_line(text: str) -> str | None:
    """Filter bare DHU prompt lines.

    Returns None for pure-noise lines (just ``> `` prompts with no content).
    Everything else passes through unchanged — including ``> command``
    lines which represent commands sent to the DHU.
    """
    stripped = text.strip()
    cleaned = stripped
    while cleaned.startswith("> "):
        cleaned = cleaned[2:]
    if cleaned == ">" or cleaned == "":
        return None
    return stripped


@dataclass
class LogEntry:
    """A single log line with its source."""

    source: str  # "dhu", "emulator", or "service"
    text: str


class LogCollector:
    """Reads and tails log files for a given instance."""

    def __init__(self, service_log_path: str | None = None) -> None:
        self._service_log_path = service_log_path

    def get_sources(self, record: InstanceRecord) -> dict[str, str]:
        """Return {source_name: file_path} for available log sources."""
        sources: dict[str, str] = {}
        if record.log_path and os.path.exists(record.log_path):
            sources["dhu"] = record.log_path
        emu_path = emu_log_path(record.name)
        if os.path.exists(emu_path):
            sources["emulator"] = emu_path
        if self._service_log_path and os.path.exists(self._service_log_path):
            sources["service"] = self._service_log_path
        return sources

    def read_recent(
        self,
        record: InstanceRecord,
        max_lines_per_source: int = 200,
        sources: set[str] | None = None,
    ) -> list[LogEntry]:
        """Read recent log lines from all (or filtered) sources."""
        available = self.get_sources(record)
        entries: list[LogEntry] = []
        for source_name, path in available.items():
            if sources and source_name not in sources:
                continue
            try:
                # DHU logs contain prompt noise that gets filtered out, so
                # over-read to compensate and then trim back.
                maxlen = max_lines_per_source
                if source_name == "dhu":
                    maxlen = max_lines_per_source * _DHU_OVERREAD_FACTOR
                with open(path, "r", errors="replace") as f:
                    tail = collections.deque(f, maxlen=maxlen)
                source_entries: list[LogEntry] = []
                for line in tail:
                    text = line.rstrip("\n")
                    if source_name == "dhu":
                        text = _clean_dhu_line(text)
                        if text is None:
                            continue
                    source_entries.append(
                        LogEntry(source=source_name, text=text)
                    )
                # Trim to requested limit (over-read may exceed it when
                # fewer lines than expected were noise).
                entries.extend(source_entries[-max_lines_per_source:])
            except OSError:
                pass
        return entries

    def tail(
        self,
        store: InstanceStore,
        instance_name: str,
        sources: set[str] | None = None,
        poll_interval: float = 0.5,
    ) -> Iterator[LogEntry | None]:
        """Yield new log lines as they appear, or None on idle polls.

        Accepts the *store* and *instance_name* rather than a snapshot record
        so that periodic rescans always see the latest log paths (e.g. after
        a DHU restart changes ``log_path``).

        Terminates (returns) if the instance is removed from the store.
        """
        record = store.get(instance_name)
        if record is None:
            return
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

                # Periodically re-scan for new/changed sources
                now = time.monotonic()
                if now - last_rescan >= _SOURCE_RESCAN_INTERVAL:
                    last_rescan = now
                    # Re-fetch the record to pick up path changes
                    # (e.g. DHU restart assigns a new log_path).
                    record = store.get(instance_name)
                    if record is None:
                        # Instance was deleted; stop tailing.
                        return
                    current_sources = self.get_sources(record)
                    for src_name, src_path in current_sources.items():
                        if sources and src_name not in sources:
                            continue
                        existing = positions.get(src_name)
                        if existing is None:
                            # Brand-new source
                            try:
                                fh = open(src_path, "r", errors="replace")
                                fh.seek(0, 2)
                                positions[src_name] = (src_path, fh)
                            except OSError:
                                pass
                        elif existing[0] != src_path:
                            # Path changed (e.g. DHU restart) — reopen
                            existing[1].close()
                            try:
                                fh = open(src_path, "r", errors="replace")
                                fh.seek(0, 2)
                                positions[src_name] = (src_path, fh)
                            except OSError:
                                del positions[src_name]
        finally:
            for _, (_, fh) in positions.items():
                fh.close()


def emu_log_path(name: str) -> str:
    """Return the standard emulator log path for the given instance name."""
    return f"/tmp/emu_{name}.log"
