"""Manages subprocess calls for starting/stopping emulator + DHU pairs."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

from instance_manager.src.instance_store import (
    InstanceRecord,
    InstanceStore,
    RUNNING,
    ERROR,
)
from instance_manager.src.port_allocator import PortSlot

log = logging.getLogger(__name__)

_DEFAULT_BOOT_TIMEOUT = 60
_DEFAULT_DHU_TIMEOUT = 30
_DEFAULT_SCREENSHOT_TIMEOUT = 5
_DESTROY_GRACEFUL_TIMEOUT = 5
_DESTROY_EMULATOR_TIMEOUT = 10


@dataclass
class _ProcessHandles:
    """Live Popen objects for an instance's child processes."""

    emulator: Optional[subprocess.Popen] = None
    dhu: Optional[subprocess.Popen] = None
    keeper: Optional[subprocess.Popen] = None
    socat: Optional[subprocess.Popen] = None


class SubprocessRunner:
    """Wrapper around subprocess calls. Override in tests."""

    def run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(args, **kwargs)

    def popen(self, args: list[str], **kwargs) -> subprocess.Popen:
        return subprocess.Popen(args, **kwargs)

    def pipe_write(self, pipe_path: str, text: str) -> None:
        """Write a line to a named pipe."""
        with open(pipe_path, "w") as pipe:
            pipe.write(text + "\n")


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
        self._handles: dict[str, _ProcessHandles] = {}
        self._handles_lock = threading.Lock()

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

        handles = _ProcessHandles()
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

            emu_log_path = f"/tmp/emu_{name}.log"
            emu_log_file = open(emu_log_path, "w")
            try:
                emu_proc = self._runner.popen(
                    emu_args,
                    stdout=emu_log_file,
                    stderr=emu_log_file,
                )
            finally:
                emu_log_file.close()
            handles.emulator = emu_proc
            self._store.update(name, emulator_pid=emu_proc.pid)

            # 3. Wait for boot
            self._wait_for_boot(serial)

            # 3b. Verify snapshot sentinel (detects cold-boot vs snapshot resume)
            if snapshot_name:
                self._check_snapshot_sentinel(serial)

            # 3c. Start socat to expose ADB on all interfaces for remote access.
            # The emulator binds ADB to 127.0.0.1 only; socat makes it
            # reachable from Docker sandbox agents via Tailscale.
            socat_proc = self._runner.popen(
                [
                    "socat",
                    f"TCP-LISTEN:{ports.adb_port},bind=0.0.0.0,reuseaddr,fork",
                    f"TCP:127.0.0.1:{ports.adb_port}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            handles.socat = socat_proc
            self._store.update(name, socat_pid=socat_proc.pid)

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
            handles.keeper = keeper_proc

            android_home = os.environ.get("ANDROID_HOME", "")
            dhu_path = os.path.join(
                android_home, "extras", "google", "auto", "desktop-head-unit"
            )
            dhu_flags = f"--adb={ports.aa_forward_port}"
            if not headful:
                dhu_flags += " --headless"
            dhu_proc = self._runner.popen(
                ["bash", "-c", f"{dhu_path} {dhu_flags} < {pipe_path} > {log_path} 2>&1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            handles.dhu = dhu_proc

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

            with self._handles_lock:
                self._handles[name] = handles

            return self._store.get(name)

        except Exception:
            # Best-effort cleanup of any already-started processes.
            for proc in [handles.dhu, handles.keeper, handles.socat, handles.emulator]:
                if proc is not None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
            self._store.update(name, state=ERROR)
            raise

    def destroy(self, record: InstanceRecord) -> None:
        """Stop an emulator + DHU pair and clean up resources.

        Uses retained Popen handles for graceful shutdown when available,
        falling back to PID-based kill for instances started before the
        manager was restarted.
        """
        serial = f"emulator-{record.emulator_console_port}"

        with self._handles_lock:
            handles = self._handles.pop(record.name, None)

        if handles:
            self._destroy_via_handles(handles, serial, record)
        else:
            self._destroy_via_pids(record, serial)

        # Remove port forward
        self._runner.run(
            ["adb", "-s", serial, "forward", "--remove",
             f"tcp:{record.aa_forward_port}"],
            capture_output=True,
        )

        # Clean up files
        emu_log_path = f"/tmp/emu_{record.name}.log"
        for path in [record.pipe_path, record.log_path, emu_log_path]:
            if path:
                self._runner.run(
                    ["rm", "-f", path], capture_output=True
                )

    def _destroy_via_handles(
        self,
        handles: _ProcessHandles,
        serial: str,
        record: InstanceRecord,
    ) -> None:
        """Graceful shutdown using retained Popen objects."""
        # 1. DHU — kill the whole process group (bash wrapper + DHU binary)
        if handles.dhu and handles.dhu.poll() is None:
            try:
                pgid = os.getpgid(handles.dhu.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    handles.dhu.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
                    handles.dhu.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
            except (OSError, subprocess.TimeoutExpired):
                log.warning("Failed to stop DHU process group for %s", record.name)

        # 2. Keeper
        if handles.keeper and handles.keeper.poll() is None:
            handles.keeper.terminate()
            try:
                handles.keeper.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
            except subprocess.TimeoutExpired:
                handles.keeper.kill()
                handles.keeper.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)


        # 3. Socat ADB forwarder
        if handles.socat and handles.socat.poll() is None:
            handles.socat.terminate()
            try:
                handles.socat.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
            except subprocess.TimeoutExpired:
                handles.socat.kill()
                handles.socat.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
        # 4. Emulator — ask adb to shut it down cleanly first
        if handles.emulator and handles.emulator.poll() is None:
            self._runner.run(
                ["adb", "-s", serial, "emu", "kill"],
                capture_output=True,
            )
            try:
                handles.emulator.wait(timeout=_DESTROY_EMULATOR_TIMEOUT)
            except subprocess.TimeoutExpired:
                handles.emulator.terminate()
                try:
                    handles.emulator.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
                except subprocess.TimeoutExpired:
                    handles.emulator.kill()
                    handles.emulator.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)

    def _destroy_via_pids(
        self, record: InstanceRecord, serial: str
    ) -> None:
        """Fallback: kill by PID when Popen handles are unavailable."""
        if record.dhu_pid:
            self._runner.run(
                ["kill", str(record.dhu_pid)],
                capture_output=True,
            )
        if record.keeper_pid:
            self._runner.run(
                ["kill", str(record.keeper_pid)],
                capture_output=True,
            )
        if record.socat_pid:
            self._runner.run(
                ["kill", str(record.socat_pid)],
                capture_output=True,
            )
        self._runner.run(
            ["adb", "-s", serial, "emu", "kill"],
            capture_output=True,
        )

    def restart_dhu(self, record: InstanceRecord) -> InstanceRecord:
        """Kill the DHU + keeper and spawn fresh ones.

        The emulator and ADB forward are left untouched. After the new DHU
        completes its SSL handshake and acquires video focus, fresh screenshots
        are captured and the store is updated.
        """
        name = record.name
        pipe_path = record.pipe_path or f"/tmp/dhu_{name}_pipe"
        log_path = record.log_path or f"/tmp/dhu_{name}.log"

        with self._handles_lock:
            handles = self._handles.get(name)

        # 1. Kill old DHU + keeper
        if handles:
            if handles.dhu and handles.dhu.poll() is None:
                try:
                    pgid = os.getpgid(handles.dhu.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    try:
                        handles.dhu.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        os.killpg(pgid, signal.SIGKILL)
                        handles.dhu.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
                except (OSError, subprocess.TimeoutExpired):
                    log.warning("Failed to stop old DHU for %s", name)

            if handles.keeper and handles.keeper.poll() is None:
                handles.keeper.terminate()
                try:
                    handles.keeper.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
                except subprocess.TimeoutExpired:
                    handles.keeper.kill()
                    handles.keeper.wait(timeout=_DESTROY_GRACEFUL_TIMEOUT)
        else:
            # Fallback: kill by PID
            if record.dhu_pid:
                self._runner.run(
                    ["kill", str(record.dhu_pid)], capture_output=True,
                )
            if record.keeper_pid:
                self._runner.run(
                    ["kill", str(record.keeper_pid)], capture_output=True,
                )

        # 2. Remove old pipe + log, recreate pipe
        self._runner.run(["rm", "-f", pipe_path], capture_output=True)
        self._runner.run(["rm", "-f", log_path], capture_output=True)
        self._runner.run(["mkfifo", pipe_path], capture_output=True)

        # 3. Spawn new keeper + DHU
        keeper_proc = self._runner.popen(
            ["bash", "-c", f"while true; do sleep 3600; done > {pipe_path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        android_home = os.environ.get("ANDROID_HOME", "")
        dhu_path = os.path.join(
            android_home, "extras", "google", "auto", "desktop-head-unit",
        )
        dhu_flags = f"--adb={record.aa_forward_port}"
        if not record.headful:
            dhu_flags += " --headless"
        dhu_proc = self._runner.popen(
            ["bash", "-c", f"{dhu_path} {dhu_flags} < {pipe_path} > {log_path} 2>&1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # 4. Update handles
        with self._handles_lock:
            if name in self._handles:
                self._handles[name].dhu = dhu_proc
                self._handles[name].keeper = keeper_proc
            else:
                self._handles[name] = _ProcessHandles(
                    dhu=dhu_proc, keeper=keeper_proc,
                )

        # 5. Update store with new PIDs
        self._store.update(
            name,
            dhu_pid=dhu_proc.pid,
            keeper_pid=keeper_proc.pid,
            pipe_path=pipe_path,
            log_path=log_path,
        )

        # 6. Wait for SSL handshake
        self._wait_for_dhu(log_path)

        # 7. Capture fresh screenshots
        serial = f"emulator-{record.emulator_console_port}"
        dhu_png = self._wait_for_dhu_screenshot(name, pipe_path)
        emu_png = self.emulator_screenshot_to_bytes(serial)
        now_ms = int(time.time() * 1000)
        self._store.update(
            name,
            last_screenshot_png=dhu_png,
            last_emulator_screenshot_png=emu_png,
            last_screenshot_at_ms=now_ms,
        )

        return self._store.get(name)

    def check_health(self, name: str) -> bool:
        """Check whether all tracked child processes for *name* are alive.

        Returns True if no handles are tracked (optimistic — we can't tell)
        or if all tracked processes are still running. Returns False if any
        child has exited.
        """
        with self._handles_lock:
            handles = self._handles.get(name)
        if handles is None:
            return True
        for proc in [handles.emulator, handles.dhu, handles.keeper, handles.socat]:
            if proc is not None and proc.poll() is not None:
                return False
        return True

    def dhu_command(
        self,
        record: InstanceRecord,
        command: str,
        capture_screenshot: bool,
    ) -> bytes:
        """Send a console command to the DHU via the named pipe.

        Returns screenshot PNG bytes if capture_screenshot is True, else b"".
        """
        if not record.pipe_path:
            raise RuntimeError(
                f"Instance '{record.name}' has no pipe path"
            )

        self._runner.pipe_write(record.pipe_path, command)

        if capture_screenshot:
            time.sleep(1)  # let UI settle after tap/keycode
            return self.screenshot_to_bytes(record.name, record.pipe_path)

        return b""

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
        self._runner.pipe_write(pipe_path, f"screenshot {screenshot_path}")

        # Poll for file (check size > 0 to avoid reading a partially-created file)
        deadline = time.time() + _DEFAULT_SCREENSHOT_TIMEOUT
        while time.time() < deadline:
            if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
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
            self._runner.pipe_write(pipe_path, f"screenshot {screenshot_path}")
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
