"""Instance cleanup utilities for shutdown and orphan detection."""

from __future__ import annotations

import logging
import subprocess

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle
from instance_manager.src.instance_store import InstanceStore

log = logging.getLogger(__name__)


def shutdown_all_instances(
    store: InstanceStore, lifecycle: EmulatorLifecycle
) -> None:
    """Destroy all tracked instances. Best-effort, logs failures."""
    for record in store.list_all():
        try:
            log.info("Shutting down instance %s", record.name)
            lifecycle.destroy(record)
        except Exception:
            log.warning(
                "Failed to destroy instance %s during shutdown",
                record.name,
                exc_info=True,
            )


def kill_orphan_emulators() -> None:
    """Kill leftover emulator processes from a previous run.

    Searches for emulator processes and kills them so they don't conflict
    with newly created instances.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-af", "emulator.*@"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return

        for line in result.stdout.strip().splitlines():
            pid = line.split()[0]
            log.info("Killing orphan emulator process %s: %s", pid, line)
            try:
                subprocess.run(
                    ["kill", "-9", pid],
                    capture_output=True,
                )
            except OSError:
                log.warning("Failed to kill orphan PID %s", pid)
    except OSError:
        log.debug("pgrep not available, skipping orphan detection")
