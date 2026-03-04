"""Thread-safe instance state management."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional


# Mirror the proto enum values for in-memory state.
CREATING = 1
RUNNING = 2
ERROR = 3
DESTROYING = 4


@dataclass
class InstanceRecord:
    """In-memory record for a single emulator + DHU instance."""

    name: str
    state: int  # One of CREATING, RUNNING, ERROR, DESTROYING
    emulator_console_port: int
    adb_port: int
    aa_forward_port: int
    headful: bool
    created_at_ms: int
    avd_name: str
    emulator_pid: Optional[int] = None
    dhu_pid: Optional[int] = None
    keeper_pid: Optional[int] = None
    socat_pid: Optional[int] = None
    pipe_path: Optional[str] = None
    log_path: Optional[str] = None
    last_screenshot_png: Optional[bytes] = None
    last_emulator_screenshot_png: Optional[bytes] = None
    last_screenshot_at_ms: Optional[int] = None


class InstanceStore:
    """Thread-safe store mapping instance name to InstanceRecord."""

    def __init__(self) -> None:
        self._instances: dict[str, InstanceRecord] = {}
        self._lock = threading.Lock()

    def create(
        self,
        name: str,
        emulator_console_port: int,
        adb_port: int,
        aa_forward_port: int,
        headful: bool,
        created_at_ms: int,
        avd_name: str,
    ) -> InstanceRecord:
        """Add a new instance in CREATING state.

        Raises:
            ValueError: If an instance with the same name already exists.
        """
        with self._lock:
            if name in self._instances:
                raise ValueError(f"Instance '{name}' already exists")
            record = InstanceRecord(
                name=name,
                state=CREATING,
                emulator_console_port=emulator_console_port,
                adb_port=adb_port,
                aa_forward_port=aa_forward_port,
                headful=headful,
                created_at_ms=created_at_ms,
                avd_name=avd_name,
            )
            self._instances[name] = record
            return record

    def get(self, name: str) -> Optional[InstanceRecord]:
        """Get an instance by name, or None if not found."""
        with self._lock:
            return self._instances.get(name)

    def list_all(self) -> list[InstanceRecord]:
        """Return all instances."""
        with self._lock:
            return list(self._instances.values())

    def update(self, name: str, **kwargs) -> None:
        """Update fields on an existing instance.

        Raises:
            KeyError: If the instance does not exist.
        """
        with self._lock:
            record = self._instances.get(name)
            if record is None:
                raise KeyError(f"Instance '{name}' not found")
            for key, value in kwargs.items():
                if not hasattr(record, key):
                    raise AttributeError(
                        f"InstanceRecord has no field '{key}'"
                    )
                setattr(record, key, value)

    def remove(self, name: str) -> None:
        """Remove an instance from the store.

        Raises:
            KeyError: If the instance does not exist.
        """
        with self._lock:
            if name not in self._instances:
                raise KeyError(f"Instance '{name}' not found")
            del self._instances[name]

    def get_running(self) -> list[InstanceRecord]:
        """Return all instances in RUNNING state."""
        with self._lock:
            return [
                r for r in self._instances.values()
                if r.state == RUNNING
            ]
