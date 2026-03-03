"""Manages subprocess calls for starting/stopping emulator + DHU pairs."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional

from instance_manager.src.instance_store import (
    InstanceRecord,
    InstanceStore,
    RUNNING,
    ERROR,
)
from instance_manager.src.port_allocator import PortSlot


_DEFAULT_BOOT_TIMEOUT = 60
_DEFAULT_DHU_TIMEOUT = 12
_DEFAULT_SCREENSHOT_TIMEOUT = 5


class SubprocessRunner:
    """Wrapper around subprocess calls. Override in tests."""

    def run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(args, **kwargs)

    def popen(self, args: list[str], **kwargs) -> subprocess.Popen:
        return subprocess.Popen(args, **kwargs)


class EmulatorLifecycle:
    """Manages emulator + DHU instance lifecycle."""

    def __init__(
        self,
        store: InstanceStore,
        runner: Optional[SubprocessRunner] = None,
        boot_timeout: int = _DEFAULT_BOOT_TIMEOUT,
        dhu_timeout: int = _DEFAULT_DHU_TIMEOUT,
    ) -> None:
        self._store = store
        self._runner = runner or SubprocessRunner()
        self._boot_timeout = boot_timeout
        self._dhu_timeout = dhu_timeout

    def create(
        self,
        name: str,
        avd_name: str,
        snapshot_name: str,
        headful: bool,
        ports: PortSlot,
    ) -> InstanceRecord:
        """Start an emulator + DHU pair.

        Updates the instance record in the store as it progresses.
        On failure, sets state to ERROR and raises.
        """
        serial = f"emulator-{ports.console_port}"
        pipe_path = f"/tmp/dhu_{name}_pipe"
        log_path = f"/tmp/dhu_{name}.log"

        try:
            # 1. Clear crash DB
            self._runner.run(
                ["bash", "-c", f"rm -rf /tmp/android-$USER/emu-crash-*.db"],
                capture_output=True,
            )

            # 2. Start emulator
            emu_args = [
                "emulator", f"@{avd_name}",
                "-read-only",
                "-port", str(ports.console_port),
                "-snapshot", snapshot_name,
                "-no-boot-anim",
            ]
            if not headful:
                emu_args.append("-no-window")

            emu_proc = self._runner.popen(
                emu_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._store.update(name, emulator_pid=emu_proc.pid)

            # 3. Wait for boot
            self._wait_for_boot(serial)

            # 3b. Verify snapshot sentinel (detects cold-boot vs snapshot resume)
            self._check_snapshot_sentinel(serial)

            # 4. Forward AA port
            self._runner.run(
                ["adb", "-s", serial, "forward",
                 f"tcp:{ports.aa_forward_port}", "tcp:5277"],
                capture_output=True,
                check=True,
            )

            # 5. Start DHU via named pipe
            self._runner.run(["mkfifo", pipe_path], capture_output=True)

            keeper_proc = self._runner.popen(
                ["bash", "-c", f"while true; do sleep 3600; done > {pipe_path}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            android_home = os.environ.get("ANDROID_HOME", "")
            dhu_path = os.path.join(
                android_home, "extras", "google", "auto", "desktop-head-unit"
            )
            dhu_proc = self._runner.popen(
                ["bash", "-c", f"{dhu_path} < {pipe_path} > {log_path} 2>&1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self._store.update(
                name,
                dhu_pid=dhu_proc.pid,
                keeper_pid=keeper_proc.pid,
                pipe_path=pipe_path,
                log_path=log_path,
            )

            # 6. Wait for DHU connected
            self._wait_for_dhu(log_path)

            # 7. Initial screenshot
            screenshot_png = self.screenshot_to_bytes(name, pipe_path)
            self._store.update(
                name,
                state=RUNNING,
                last_screenshot_png=screenshot_png,
                last_screenshot_at_ms=int(time.time() * 1000),
            )

            return self._store.get(name)

        except Exception:
            self._store.update(name, state=ERROR)
            raise

    def destroy(self, record: InstanceRecord) -> None:
        """Stop an emulator + DHU pair and clean up resources."""
        serial = f"emulator-{record.emulator_console_port}"

        # Kill DHU
        if record.dhu_pid:
            self._runner.run(
                ["kill", str(record.dhu_pid)],
                capture_output=True,
            )

        # Kill keeper
        if record.keeper_pid:
            self._runner.run(
                ["kill", str(record.keeper_pid)],
                capture_output=True,
            )

        # Kill emulator
        self._runner.run(
            ["adb", "-s", serial, "emu", "kill"],
            capture_output=True,
        )

        # Remove port forward
        self._runner.run(
            ["adb", "-s", serial, "forward", "--remove",
             f"tcp:{record.aa_forward_port}"],
            capture_output=True,
        )

        # Clean up files
        for path in [record.pipe_path, record.log_path]:
            if path:
                self._runner.run(
                    ["rm", "-f", path], capture_output=True
                )

    def screenshot(self, record: InstanceRecord) -> bytes:
        """Capture a DHU screenshot and return PNG bytes."""
        if not record.pipe_path:
            raise RuntimeError(
                f"Instance '{record.name}' has no pipe path"
            )
        return self.screenshot_to_bytes(record.name, record.pipe_path)

    def screenshot_to_bytes(self, name: str, pipe_path: str) -> bytes:
        """Send screenshot command to DHU and read the resulting PNG."""
        screenshot_path = f"/tmp/dhu_{name}_screenshot.png"

        # Remove existing screenshot
        self._runner.run(
            ["rm", "-f", screenshot_path], capture_output=True
        )

        # Send screenshot command via pipe
        self._runner.run(
            ["bash", "-c", f'echo "screenshot {screenshot_path}" > {pipe_path}'],
            capture_output=True,
        )

        # Poll for file
        deadline = time.time() + _DEFAULT_SCREENSHOT_TIMEOUT
        while time.time() < deadline:
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    return f.read()
            time.sleep(0.2)

        raise TimeoutError(
            f"Screenshot file not created within {_DEFAULT_SCREENSHOT_TIMEOUT}s"
        )

    def _wait_for_boot(self, serial: str) -> None:
        """Poll adb until sys.boot_completed is 1."""
        deadline = time.time() + self._boot_timeout
        while time.time() < deadline:
            result = self._runner.run(
                ["adb", "-s", serial, "shell",
                 "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip() == "1":
                return
            time.sleep(1)
        raise TimeoutError(
            f"Emulator {serial} did not boot within {self._boot_timeout}s"
        )

    def _check_snapshot_sentinel(self, serial: str) -> None:
        """Verify the snapshot sentinel file exists on the emulator.

        The ``aa_ready`` snapshot has ``.vanpilot_snapshot_sentinel`` baked in
        at ``/data/local/tmp/``.  If the file is absent the emulator cold-booted
        (i.e. the snapshot was not loaded) and the caller should not proceed.
        """
        result = self._runner.run(
            ["adb", "-s", serial, "shell",
             "ls", "/data/local/tmp/.vanpilot_snapshot_sentinel"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Snapshot sentinel missing on {serial}: emulator cold-booted "
                "instead of resuming snapshot. Check -gpu flag and AVD snapshot name."
            )

    def _wait_for_dhu(self, log_path: str) -> None:
        """Poll DHU log until 'connected' appears."""
        deadline = time.time() + self._dhu_timeout
        while time.time() < deadline:
            try:
                with open(log_path, "r") as f:
                    if "connected" in f.read().lower():
                        return
            except FileNotFoundError:
                pass
            time.sleep(0.5)
        raise TimeoutError(
            f"DHU did not connect within {self._dhu_timeout}s"
        )
