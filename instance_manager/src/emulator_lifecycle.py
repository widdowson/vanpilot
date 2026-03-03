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
_DEFAULT_DHU_TIMEOUT = 30
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
            gpu_mode = self._resolve_gpu_mode(avd_name, snapshot_name)
            emu_args = [
                "emulator", f"@{avd_name}",
                "-read-only",
                "-port", str(ports.console_port),
                "-snapshot", snapshot_name,
                "-no-boot-anim",
                "-gpu", gpu_mode,
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

            # 6. Wait for DHU connected + SSL handshake
            self._wait_for_dhu(log_path)

            # 7. Wait for DHU video focus, then capture both screenshots.
            # Video focus is granted asynchronously after SSL — poll until
            # the DHU successfully produces a screenshot file.
            dhu_png = self._wait_for_dhu_screenshot(name, pipe_path)
            emu_png = self.emulator_screenshot_to_bytes(serial)
            now_ms = int(time.time() * 1000)
            self._store.update(
                name,
                state=RUNNING,
                last_screenshot_png=dhu_png,
                last_emulator_screenshot_png=emu_png,
                last_screenshot_at_ms=now_ms,
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

    def emulator_screenshot_to_bytes(self, serial: str) -> bytes:
        """Capture the emulator phone screen via adb screencap."""
        screenshot_path = f"/tmp/emu_{serial}_screenshot.png"
        self._runner.run(
            ["rm", "-f", screenshot_path], capture_output=True
        )
        self._runner.run(
            ["bash", "-c",
             f"adb -s {serial} exec-out screencap -p > {screenshot_path}"],
            capture_output=True,
        )
        deadline = time.time() + _DEFAULT_SCREENSHOT_TIMEOUT
        while time.time() < deadline:
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                with open(screenshot_path, "rb") as f:
                    return f.read()
            time.sleep(0.2)
        return b""

    def _wait_for_dhu_screenshot(
        self, name: str, pipe_path: str, timeout: int = 90, interval: float = 2,
    ) -> bytes:
        """Poll the DHU screenshot command until video focus is granted."""
        deadline = time.time() + timeout
        screenshot_path = f"/tmp/dhu_{name}_screenshot.png"
        while time.time() < deadline:
            self._runner.run(["rm", "-f", screenshot_path], capture_output=True)
            self._runner.run(
                ["bash", "-c", f'echo "screenshot {screenshot_path}" > {pipe_path}'],
                capture_output=True,
            )
            time.sleep(interval)
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
                with open(screenshot_path, "rb") as f:
                    return f.read()
        raise TimeoutError(
            f"DHU did not acquire video focus within {timeout}s"
        )

    def _resolve_gpu_mode(self, avd_name: str, snapshot_name: str) -> str:
        """Determine the GPU mode needed to load the snapshot.

        Reads the saved command-line args from the snapshot's protobuf
        metadata first (most accurate — captures CLI overrides). Falls back
        to ``hw.gpu.mode`` in the AVD's ``config.ini``.
        """
        gpu = self._read_gpu_from_snapshot(avd_name, snapshot_name)
        if gpu:
            return gpu
        return self._read_gpu_from_config(avd_name)

    def _read_gpu_from_snapshot(
        self, avd_name: str, snapshot_name: str
    ) -> Optional[str]:
        """Extract the -gpu flag from the snapshot's saved command line."""
        avd_home = os.environ.get(
            "ANDROID_AVD_HOME",
            os.path.expanduser("~/.android/avd"),
        )
        snapshot_pb = os.path.join(
            avd_home, f"{avd_name}.avd", "snapshots",
            snapshot_name, "snapshot.pb",
        )
        try:
            with open(snapshot_pb, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return None

        # Extract printable ASCII string runs from the protobuf binary.
        strings: list[str] = []
        current: list[str] = []
        for byte in data:
            if 32 <= byte <= 126:
                current.append(chr(byte))
            else:
                if len(current) >= 2:
                    strings.append("".join(current))
                current = []
        if len(current) >= 2:
            strings.append("".join(current))

        for i, s in enumerate(strings):
            if s == "-gpu" and i + 1 < len(strings):
                return strings[i + 1]
        return None

    def _read_gpu_from_config(self, avd_name: str) -> str:
        """Read hw.gpu.mode from the AVD's config.ini.

        Raises:
            RuntimeError: if config.ini is missing or hw.gpu.mode is absent.
        """
        avd_home = os.environ.get(
            "ANDROID_AVD_HOME",
            os.path.expanduser("~/.android/avd"),
        )
        config_path = os.path.join(avd_home, f"{avd_name}.avd", "config.ini")
        try:
            with open(config_path) as f:
                for line in f:
                    key, _, value = line.partition("=")
                    if key.strip() == "hw.gpu.mode":
                        return value.strip()
        except FileNotFoundError:
            raise RuntimeError(
                f"AVD config not found: {config_path}"
            )
        raise RuntimeError(
            f"hw.gpu.mode not found in {config_path}"
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
        """Poll DHU log until SSL handshake completes.

        Waits for 'verify returned' which indicates the full SSL negotiation
        is done and the video channel is nearly ready. Waiting only for
        'connected' is too early — screenshot commands fail with
        'Don't have video focus' before SSL finishes.
        """
        deadline = time.time() + self._dhu_timeout
        while time.time() < deadline:
            try:
                with open(log_path, "r") as f:
                    content = f.read().lower()
                    if "verify returned" in content:
                        return
            except FileNotFoundError:
                pass
            time.sleep(0.5)
        raise TimeoutError(
            f"DHU did not complete SSL handshake within {self._dhu_timeout}s"
        )
