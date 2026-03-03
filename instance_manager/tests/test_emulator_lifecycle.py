"""Tests for EmulatorLifecycle with mocked SubprocessRunner."""

import subprocess
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

        with patch.object(lifecycle, "_wait_for_dhu"):
            with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
                lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        # Check emulator popen was called
        emu_call = runner.popen_calls[0]
        emu_args = emu_call[0]
        self.assertEqual(emu_args[0], "emulator")
        self.assertIn("@test_avd", emu_args)
        self.assertIn("-port", emu_args)
        self.assertIn("5554", emu_args)
        self.assertIn("-no-window", emu_args)

    def test_create_headful_omits_no_window(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, True, 1000, "test_avd")

        with patch.object(lifecycle, "_wait_for_dhu"):
            with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
                lifecycle.create("test", "test_avd", "aa_ready", True, ports)

        emu_call = runner.popen_calls[0]
        emu_args = emu_call[0]
        self.assertNotIn("-no-window", emu_args)

    def test_create_calls_adb_forward(self):
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_wait_for_dhu"):
            with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
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

        with patch.object(lifecycle, "_wait_for_dhu"):
            with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
                record = lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertEqual(record.state, RUNNING)

    def test_create_boot_timeout_sets_error(self):
        store, runner, lifecycle = self._make_lifecycle(boot_ready=False)
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with self.assertRaises(TimeoutError):
            lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertEqual(store.get("test").state, ERROR)

    def test_create_sentinel_present_succeeds(self):
        """create() completes normally when the snapshot sentinel file exists."""
        store, runner, lifecycle = self._make_lifecycle()
        ports = self._make_ports()
        store.create("test", 5554, 5555, 5277, False, 1000, "test_avd")

        with patch.object(lifecycle, "_wait_for_dhu"):
            with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
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
            with patch.object(lifecycle, "_wait_for_dhu"):
                with patch.object(lifecycle, "screenshot_to_bytes", return_value=b"png"):
                    lifecycle.create("test", "test_avd", "aa_ready", False, ports)

        self.assertIn("cold-booted", str(ctx.exception))
        self.assertEqual(store.get("test").state, ERROR)

    def test_destroy_kills_processes(self):
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


if __name__ == "__main__":
    unittest.main()
