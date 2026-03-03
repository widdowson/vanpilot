"""Collects and tails log files for emulator instances."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterator, Optional

from instance_manager.src.instance_store import InstanceRecord


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
        max_lines: int = 200,
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
                    lines = f.readlines()
                for line in lines[-max_lines:]:
                    entries.append(
                        LogEntry(source=source_name, text=line.rstrip("\n"))
                    )
            except OSError:
                pass
        return entries

    def tail(
        self,
        record: InstanceRecord,
        sources: Optional[set[str]] = None,
        poll_interval: float = 0.5,
    ) -> Iterator[LogEntry]:
        """Yield new log lines as they appear. Blocks between polls."""
        available = self.get_sources(record)
        positions: dict[str, tuple[str, object]] = {}
        for source_name, path in available.items():
            if sources and source_name not in sources:
                continue
            try:
                fh = open(path, "r", errors="replace")
                fh.seek(0, 2)  # Seek to end
                positions[source_name] = (path, fh)
            except OSError:
                pass

        try:
            while True:
                found_any = False
                for source_name, (path, fh) in positions.items():
                    for line in fh:
                        found_any = True
                        yield LogEntry(
                            source=source_name, text=line.rstrip("\n")
                        )
                if not found_any:
                    time.sleep(poll_interval)
        finally:
            for _, (_, fh) in positions.items():
                fh.close()
