"""Tests for EmulatorLifecycle with mocked SubprocessRunner."""

import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

from instance_manager.src.emulator_lifecycle import (
    EmulatorLifecycle,
    SubprocessRunner,
)
from instance_manager.src.instance_store import InstanceStore, RUNNING, ERROR
from instance_manager.src.port_allocator import PortSlot


class FakeSubprocessRunner(SubprocessRunner):
    """Records all subprocess calls for verification."""

    def __init__(self):
        self.run_calls = []
        self.popen_calls = []
        self._boot_ready = True
        self._dhu_connected = True

    def run(self, args, **kwargs):
        self.run_calls.append((args, kwargs))
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        # Simulate boot_completed check
        if "getprop" in args and "sys.boot_completed" in args:
            result.stdout = "1" if self._boot_ready else ""

        return result

    def popen(self, args, **kwargs):
        self.popen_calls.append((args, kwargs))
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.return_value = None  # alive
        proc.wait.return_value = 0
        return proc


class EmulatorLifecycleTest(unittest.TestCase):

    def _make_lifecycle(self, runner=None, boot_ready=True, dhu_connected=True):
        store = InstanceStore()
        if runner is None:
            runner = FakeSubprocessRunner()
            runner._boot_ready = boot_ready
            runner._dhu_connected = dhu_connected
        lifecycle = EmulatorLifecycle(
            store, runner, boot_timeout=2, dhu_timeout=2,
        )
        return store, runner, lifecycle

    def _make_ports(self):
        return PortSlot(
            slot_index=0,
            console_port=5554,
            adb_port=5555,
            aa_forward_port=5277,
        )

    def test_create_calls_emulator_with_correct_args(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        # Check emulator popen was called
        emu_call = runner.popen_calls[0]
        emu_args = emu_call[0]
        self.assertEqual(emu_args[0], "emulator")
        self.assertIn("@test_avd", emu_args)
        self.assertIn("-port", emu_args)
        self.assertIn("5554", emu_args)
        self.assertIn("-no-window", emu_args)
        self.assertIn("-gpu", emu_args)
        self.assertIn("swiftshader_indirect", emu_args)

    def test_create_headful_omits_no_window(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, True, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    lifecycle.create("test", "test_avd", "aa_ready", True, ports)

        emu_call = runner.popen_calls[0]
        emu_args = emu_call[0]
        self.assertNotIn("-no-window", emu_args)

    def test_create_calls_adb_forward(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        # Find the adb forward call
        forward_calls = [
            c for c in runner.run_calls
            if len(c[0]) > 2 and "forward" in c[0] and "tcp:5277" in c[0]
        ]
        self.assertTrue(len(forward_calls) > 0)

    def test_create_sets_running_state(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    record = lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertEqual(record.state, RUNNING)

    def test_create_boot_timeout_sets_error(self):
        store, runner, lifecycle = self._make_lifecycle(boot_ready=False)
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with self.assertRaises(TimeoutError):
                lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertEqual(store.get("test").state, ERROR)

    def test_create_sentinel_present_succeeds(self):
        """create() completes normally when the snapshot sentinel file exists."""
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    record = lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        # Sentinel check should have been issued
        sentinel_calls = [
            c for c in runner.run_calls
            if ".vanpilot_snapshot_sentinel" in " ".join(c[0])
        ]
        self.assertEqual(len(sentinel_calls), 1)
        self.assertEqual(record.state, RUNNING)

    def test_create_sentinel_absent_raises_and_sets_error(self):
        """create() raises RuntimeError with 'cold-booted' when sentinel is missing."""

        class SentinelMissingRunner(FakeSubprocessRunner):
            def run(self, args, **kwargs):
                result = super().run(args, **kwargs)
                if ".vanpilot_snapshot_sentinel" in " ".join(args):
                    result.returncode = 1
                    result.stdout = ""
                return result

        runner = SentinelMissingRunner()
        store = InstanceStore()
        lifecycle = EmulatorLifecycle(store, runner, boot_timeout=2, dhu_timeout=2)
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with self.assertRaises(RuntimeError) as ctx:
            with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
                with patch.object(lifecycle, "_wait_for_dhu"):
                    with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                        lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertIn("cold-booted", str(ctx.exception))
        self.assertEqual(store.get("test").state, ERROR)

    def test_create_skips_sentinel_when_no_snapshot(self):
        """create() skips the sentinel check when snapshot_name is empty."""
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    record = lifecycle.create("test", "test_avd", "", False, ports)

        # No sentinel check should have been issued
        sentinel_calls = [
            c for c in runner.run_calls
            if ".vanpilot_snapshot_sentinel" in " ".join(c[0])
        ]
        self.assertEqual(len(sentinel_calls), 0)
        self.assertEqual(record.state, RUNNING)

    def test_destroy_falls_back_to_pid_kill(self):
        """When no Popen handles exist, destroy falls back to kill <pid>."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        # No handles stored — simulates manager restart
        lifecycle.destroy(record)

        # Check kill calls
        kill_args = [c[0] for c in runner.run_calls if c[0][0] == "kill"]
        self.assertIn(["kill", "100"], kill_args)
        self.assertIn(["kill", "101"], kill_args)

        # Check emu kill
        emu_kills = [
            c for c in runner.run_calls
            if len(c[0]) > 2 and "emu" in c[0] and "kill" in c[0]
        ]
        self.assertTrue(len(emu_kills) > 0)

    def test_destroy_uses_popen_handles(self):
        """When Popen handles exist, destroy uses terminate/wait instead of shell kill."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        # Inject process handles
        from instance_manager.src.emulator_lifecycle import _ProcessHandles
        emu_proc = MagicMock()
        emu_proc.poll.return_value = None  # alive
        emu_proc.wait.return_value = 0

        dhu_proc = MagicMock()
        dhu_proc.pid = 100
        dhu_proc.poll.return_value = None
        dhu_proc.wait.return_value = 0

        keeper_proc = MagicMock()
        keeper_proc.poll.return_value = None
        keeper_proc.wait.return_value = 0

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=emu_proc, dhu=dhu_proc, keeper=keeper_proc,
        )

        with patch("os.getpgid", return_value=200), \
             patch("os.killpg") as mock_killpg:
            lifecycle.destroy(record)

        # DHU should be killed via process group SIGTERM
        mock_killpg.assert_any_call(200, __import__("signal").SIGTERM)
        dhu_proc.wait.assert_called()

        # Keeper should be terminated
        keeper_proc.terminate.assert_called_once()

        # Emulator should get adb emu kill then wait
        emu_kills = [
            c for c in runner.run_calls
            if len(c[0]) > 2 and "emu" in c[0] and "kill" in c[0]
        ]
        self.assertTrue(len(emu_kills) > 0)
        emu_proc.wait.assert_called()

        # Should NOT have shell kill calls (no PID fallback)
        kill_args = [c[0] for c in runner.run_calls if c[0][0] == "kill"]
        self.assertEqual(kill_args, [])

    def test_check_health_all_alive(self):
        """check_health returns True when all processes are alive."""
        store, _, lifecycle = self._make_lifecycle()
        from instance_manager.src.emulator_lifecycle import _ProcessHandles

        emu = MagicMock()
        emu.poll.return_value = None
        dhu = MagicMock()
        dhu.poll.return_value = None
        keeper = MagicMock()
        keeper.poll.return_value = None

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=emu, dhu=dhu, keeper=keeper,
        )
        self.assertTrue(lifecycle.check_health("test"))

    def test_check_health_emulator_dead(self):
        """check_health returns False when emulator has exited."""
        store, _, lifecycle = self._make_lifecycle()
        from instance_manager.src.emulator_lifecycle import _ProcessHandles

        emu = MagicMock()
        emu.poll.return_value = 1  # exited
        dhu = MagicMock()
        dhu.poll.return_value = None
        keeper = MagicMock()
        keeper.poll.return_value = None

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=emu, dhu=dhu, keeper=keeper,
        )
        self.assertFalse(lifecycle.check_health("test"))

    def test_check_health_no_handles(self):
        """check_health returns True (optimistic) when no handles are tracked."""
        store, _, lifecycle = self._make_lifecycle()
        self.assertTrue(lifecycle.check_health("unknown"))


    def test_restart_dhu_kills_old_spawns_new(self):
        """restart_dhu terminates old DHU/keeper handles and spawns new ones."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        # Inject old process handles
        from instance_manager.src.emulator_lifecycle import _ProcessHandles
        old_dhu = MagicMock()
        old_dhu.pid = 100
        old_dhu.poll.return_value = None  # alive
        old_dhu.wait.return_value = 0

        old_keeper = MagicMock()
        old_keeper.poll.return_value = None
        old_keeper.wait.return_value = 0

        emu_proc = MagicMock()
        emu_proc.poll.return_value = None

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=emu_proc, dhu=old_dhu, keeper=old_keeper,
        )

        with patch("os.getpgid", return_value=200), \
             patch("os.killpg") as mock_killpg, \
             patch.object(lifecycle, "_wait_for_dhu"), \
             patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
             patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
            updated = lifecycle.restart_dhu(record)

        # Old DHU should be killed via SIGTERM on its process group
        mock_killpg.assert_any_call(200, __import__("signal").SIGTERM)
        old_dhu.wait.assert_called()

        # Old keeper should be terminated
        old_keeper.terminate.assert_called_once()

        # New popen calls: keeper + DHU (2 popen calls)
        self.assertEqual(len(runner.popen_calls), 2)

        # mkfifo should have been called (after rm -f pipe and rm -f log)
        mkfifo_calls = [c for c in runner.run_calls if c[0][0] == "mkfifo"]
        self.assertEqual(len(mkfifo_calls), 1)

        # Handles should be updated with new procs (not the old ones)
        new_handles = lifecycle._handles["test"]
        self.assertIsNot(new_handles.dhu, old_dhu)
        self.assertIsNot(new_handles.keeper, old_keeper)
        # Emulator handle should be preserved
        self.assertIs(new_handles.emulator, emu_proc)

        # Store should have updated PIDs
        self.assertEqual(updated.state, RUNNING)

    def test_restart_dhu_pid_fallback(self):
        """restart_dhu uses kill-by-PID when no Popen handles are available."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        # No handles — simulates manager restart
        with patch.object(lifecycle, "_wait_for_dhu"), \
             patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
             patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
            lifecycle.restart_dhu(record)

        # Should have shell kill calls for old PIDs
        kill_args = [c[0] for c in runner.run_calls if c[0][0] == "kill"]
        self.assertIn(["kill", "100"], kill_args)
        self.assertIn(["kill", "101"], kill_args)


    def test_create_starts_socat_forwarder(self):
        """create() launches socat to expose ADB on 0.0.0.0."""
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        # Find the socat popen call (second popen: emulator is first, socat is second)
        socat_calls = [
            c for c in runner.popen_calls
            if c[0][0] == "socat"
        ]
        self.assertEqual(len(socat_calls), 1)
        socat_args = socat_calls[0][0]
        self.assertEqual(socat_args[0], "socat")
        self.assertIn("TCP-LISTEN:5555", socat_args[1])
        self.assertIn("bind=0.0.0.0", socat_args[1])
        self.assertEqual(socat_args[2], "TCP:127.0.0.1:5555")

    def test_create_stores_socat_pid(self):
        """create() records the socat PID in the instance store."""
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_resolve_gpu_mode", return_value="swiftshader_indirect"):
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "_wait_for_dhu_screenshot", return_value=b"png"), \
                     patch.object(lifecycle, "emulator_screenshot_to_bytes", return_value=b"png"):
                    record = lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertIsNotNone(record.socat_pid)

    def test_destroy_kills_socat_via_handles(self):
        """destroy() terminates the socat process when Popen handles exist."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            socat_pid=103,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        from instance_manager.src.emulator_lifecycle import _ProcessHandles
        socat_proc = MagicMock()
        socat_proc.poll.return_value = None
        socat_proc.wait.return_value = 0

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=MagicMock(poll=MagicMock(return_value=None), wait=MagicMock(return_value=0)),
            dhu=MagicMock(pid=100, poll=MagicMock(return_value=None), wait=MagicMock(return_value=0)),
            keeper=MagicMock(poll=MagicMock(return_value=None), wait=MagicMock(return_value=0)),
            socat=socat_proc,
        )

        with patch("os.getpgid", return_value=200), \
             patch("os.killpg"):
            lifecycle.destroy(record)

        socat_proc.terminate.assert_called_once()

    def test_destroy_kills_socat_via_pid(self):
        """destroy() kills socat by PID when no Popen handles exist."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            dhu_pid=100,
            keeper_pid=101,
            emulator_pid=102,
            socat_pid=103,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test.log",
        )
        record = store.get("test")

        lifecycle.destroy(record)

        kill_args = [c[0] for c in runner.run_calls if c[0][0] == "kill"]
        self.assertIn(["kill", "103"], kill_args)

    def test_check_health_socat_dead(self):
        """check_health returns False when the socat process has exited."""
        store, _, lifecycle = self._make_lifecycle()
        from instance_manager.src.emulator_lifecycle import _ProcessHandles

        emu = MagicMock()
        emu.poll.return_value = None
        dhu = MagicMock()
        dhu.poll.return_value = None
        keeper = MagicMock()
        keeper.poll.return_value = None
        socat = MagicMock()
        socat.poll.return_value = 1  # exited

        lifecycle._handles["test"] = _ProcessHandles(
            emulator=emu, dhu=dhu, keeper=keeper, socat=socat,
        )
        self.assertFalse(lifecycle.check_health("test"))

    def test_dhu_command_writes_to_pipe(self):
        """dhu_command writes the command string to the named pipe."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            pipe_path="/tmp/dhu_test_pipe",
            log_path="/tmp/dhu_test_cmd_echo.log",
        )
        record = store.get("test")

        # Seed the log file so we can verify the append
        os.makedirs("/tmp", exist_ok=True)
        with open("/tmp/dhu_test_cmd_echo.log", "w") as f:
            f.write("DHU connected\n")

        with patch.object(runner, "pipe_write") as mock_pw:
            result = lifecycle.dhu_command(record, "keycode home", False)

        self.assertEqual(result, b"")
        mock_pw.assert_called_once_with("/tmp/dhu_test_pipe", "keycode home")

        # Verify command was echoed to the log file
        with open("/tmp/dhu_test_cmd_echo.log") as f:
            content = f.read()
        self.assertIn("> keycode home", content)
        os.remove("/tmp/dhu_test_cmd_echo.log")

    def test_dhu_command_with_screenshot(self):
        """dhu_command captures a screenshot when requested."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(
            "test",
            state=RUNNING,
            pipe_path="/tmp/dhu_test_pipe",
        )
        record = store.get("test")

        with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"fake-png") as mock_ss, \
             patch("time.sleep"):
            result = lifecycle.dhu_command(record, "tap 300 430", True)

        self.assertEqual(result, b"fake-png")
        mock_ss.assert_called_once_with("test", "/tmp/dhu_test_pipe")

    def test_dhu_command_no_pipe_raises(self):
        """dhu_command raises RuntimeError when pipe_path is None."""
        store, runner, lifecycle = self._make_lifecycle()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")
        store.update("test", state=RUNNING)
        record = store.get("test")

        with self.assertRaises(RuntimeError) as ctx:
            lifecycle.dhu_command(record, "keycode home", False)
        self.assertIn("no pipe path", str(ctx.exception))


class InstallApkTest(unittest.TestCase):
    """Tests for EmulatorLifecycle.install_apk."""

    def _make_lifecycle(self, runner=None):
        store = InstanceStore()
        if runner is None:
            runner = FakeSubprocessRunner()
        lifecycle = EmulatorLifecycle(
            store, runner, boot_timeout=2, dhu_timeout=2,
        )
        return store, runner, lifecycle

    def _make_record(self, store, name="test"):
        store.create(name, 5554, 5555, 5277, False, 1000, "test_avd")
        store.update(name, state=RUNNING, pipe_path="/tmp/dhu_test_pipe")
        return store.get(name)

    def test_install_apk_calls_adb_install(self):
        """install_apk runs 'adb -s <serial> install -r <path>'."""
        store, runner, lifecycle = self._make_lifecycle()
        record = self._make_record(store)

        lifecycle.install_apk(record, b"fake-apk-contents")

        install_calls = [
            c for c in runner.run_calls
            if len(c[0]) >= 4 and "install" in c[0]
        ]
        self.assertEqual(len(install_calls), 1)
        args = install_calls[0][0]
        self.assertEqual(args[0], "adb")
        self.assertEqual(args[1], "-s")
        self.assertEqual(args[2], "emulator-5554")
        self.assertEqual(args[3], "install")
        self.assertEqual(args[4], "-r")
        self.assertTrue(args[5].endswith(".apk"))

    def test_install_apk_cleans_up_temp_file(self):
        """install_apk removes the temp file after completion."""
        store, runner, lifecycle = self._make_lifecycle()
        record = self._make_record(store)

        lifecycle.install_apk(record, b"PK\x03\x04fake-apk")

        install_calls = [
            c for c in runner.run_calls
            if len(c[0]) >= 4 and "install" in c[0]
        ]
        temp_path = install_calls[0][0][5]
        self.assertFalse(os.path.exists(temp_path))

    def test_install_apk_cleans_up_on_failure(self):
        """install_apk cleans up temp file even when adb install fails."""

        class FailingInstallRunner(FakeSubprocessRunner):
            def run(self, args, **kwargs):
                result = super().run(args, **kwargs)
                if "install" in args:
                    result.returncode = 1
                    result.stderr = "Failure [INSTALL_FAILED]"
                return result

        store, runner, lifecycle = self._make_lifecycle(runner=FailingInstallRunner())
        record = self._make_record(store)

        with self.assertRaises(RuntimeError) as ctx:
            lifecycle.install_apk(record, b"fake-apk")
        self.assertIn("adb install failed", str(ctx.exception))

    def test_install_apk_empty_bytes_raises(self):
        """install_apk raises ValueError when apk_data is empty."""
        store, runner, lifecycle = self._make_lifecycle()
        record = self._make_record(store)

        with self.assertRaises(ValueError) as ctx:
            lifecycle.install_apk(record, b"")
        self.assertIn("empty", str(ctx.exception).lower())


class ResolveGpuModeTest(unittest.TestCase):
    """Unit tests for EmulatorLifecycle._resolve_gpu_mode."""

    def _make_lifecycle(self):
        store = InstanceStore()
        runner = FakeSubprocessRunner()
        return EmulatorLifecycle(store, runner, boot_timeout=2, dhu_timeout=2)

    def _make_avd_dir(self, avd_home, avd_name, config_lines=None, snapshot_name=None, snapshot_args=None):
        """Helper to set up an AVD directory with optional config and snapshot."""
        avd_dir = os.path.join(avd_home, f"{avd_name}.avd")
        os.makedirs(avd_dir, exist_ok=True)
        if config_lines is not None:
            with open(os.path.join(avd_dir, "config.ini"), "w") as f:
                f.write("\n".join(config_lines) + "\n")
        if snapshot_name and snapshot_args:
            snap_dir = os.path.join(avd_dir, "snapshots", snapshot_name)
            os.makedirs(snap_dir, exist_ok=True)
            # Write a fake snapshot.pb with the args as length-prefixed strings
            # mimicking what the emulator writes (protobuf string fields).
            # Tag 0x0a (field 1, wire type 2) is non-printable, ensuring
            # the ASCII string scanner cleanly splits args.
            pb_data = b""
            for arg in snapshot_args:
                encoded = arg.encode("ascii")
                pb_data += b"\x0a" + bytes([len(encoded)]) + encoded
            with open(os.path.join(snap_dir, "snapshot.pb"), "wb") as f:
                f.write(pb_data)

    def test_prefers_snapshot_gpu_over_config(self):
        """_resolve_gpu_mode reads from snapshot.pb when -gpu flag is present."""
        lifecycle = self._make_lifecycle()
        with tempfile.TemporaryDirectory() as avd_home:
            self._make_avd_dir(
                avd_home, "test_avd",
                config_lines=["hw.gpu.mode=auto"],
                snapshot_name="aa_ready",
                snapshot_args=["emulator", "@test_avd", "-gpu", "swiftshader_indirect", "-snapshot", "aa_ready"],
            )
            with patch.dict(os.environ, {"ANDROID_AVD_HOME": avd_home}):
                result = lifecycle._resolve_gpu_mode("test_avd", "aa_ready")
        self.assertEqual(result, "swiftshader_indirect")

    def test_falls_back_to_config_when_snapshot_has_no_gpu(self):
        """_resolve_gpu_mode falls back to config.ini when snapshot lacks -gpu."""
        lifecycle = self._make_lifecycle()
        with tempfile.TemporaryDirectory() as avd_home:
            self._make_avd_dir(
                avd_home, "test_avd",
                config_lines=["hw.gpu.mode=host"],
                snapshot_name="aa_ready",
                snapshot_args=["emulator", "@test_avd", "-snapshot", "aa_ready"],
            )
            with patch.dict(os.environ, {"ANDROID_AVD_HOME": avd_home}):
                result = lifecycle._resolve_gpu_mode("test_avd", "aa_ready")
        self.assertEqual(result, "host")

    def test_falls_back_to_config_when_no_snapshot_pb(self):
        """_resolve_gpu_mode falls back to config.ini when snapshot.pb is missing."""
        lifecycle = self._make_lifecycle()
        with tempfile.TemporaryDirectory() as avd_home:
            self._make_avd_dir(
                avd_home, "test_avd",
                config_lines=["hw.gpu.mode=swiftshader_indirect"],
            )
            with patch.dict(os.environ, {"ANDROID_AVD_HOME": avd_home}):
                result = lifecycle._resolve_gpu_mode("test_avd", "nonexistent_snap")
        self.assertEqual(result, "swiftshader_indirect")

    def test_raises_when_no_snapshot_and_no_config(self):
        """_resolve_gpu_mode raises RuntimeError when both sources fail."""
        lifecycle = self._make_lifecycle()
        with tempfile.TemporaryDirectory() as avd_home:
            with patch.dict(os.environ, {"ANDROID_AVD_HOME": avd_home}):
                with self.assertRaises(RuntimeError):
                    lifecycle._resolve_gpu_mode("missing_avd", "missing_snap")


if __name__ == "__main__":
    unittest.main()
