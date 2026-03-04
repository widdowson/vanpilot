"""Tests for server shutdown and orphan cleanup."""

import unittest
from unittest.mock import MagicMock, patch

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle
from instance_manager.src.instance_store import (
    InstanceStore,
    RUNNING,
    CREATING,
    ERROR,
)
from instance_manager.src.cleanup import (
    shutdown_all_instances,
    kill_orphan_emulators,
)


class ShutdownAllInstancesTest(unittest.TestCase):
    """Tests for shutdown_all_instances."""

    def _make_store_with_instances(self, *names_and_states):
        """Create a store populated with instances in given states."""
        store = InstanceStore()
        for i, (name, state) in enumerate(names_and_states):
            port = 5554 + i * 2
            store.create(
                name=name,
                emulator_console_port=port,
                adb_port=port + 1,
                aa_forward_port=5277 + i,
                headful=False,
                created_at_ms=1000 + i,
                avd_name="test_avd",
            )
            store.update(name, state=state)
        return store

    def test_destroys_all_running_instances(self):
        store = self._make_store_with_instances(
            ("inst-a", RUNNING),
            ("inst-b", RUNNING),
        )
        lifecycle = MagicMock(spec=EmulatorLifecycle)

        shutdown_all_instances(store, lifecycle)

        self.assertEqual(lifecycle.destroy.call_count, 2)
        destroyed_names = {c.args[0].name for c in lifecycle.destroy.call_args_list}
        self.assertEqual(destroyed_names, {"inst-a", "inst-b"})

    def test_destroys_instances_in_all_states(self):
        store = self._make_store_with_instances(
            ("running", RUNNING),
            ("creating", CREATING),
            ("error", ERROR),
        )
        lifecycle = MagicMock(spec=EmulatorLifecycle)

        shutdown_all_instances(store, lifecycle)

        self.assertEqual(lifecycle.destroy.call_count, 3)

    def test_continues_after_destroy_failure(self):
        store = self._make_store_with_instances(
            ("fail", RUNNING),
            ("ok", RUNNING),
        )
        lifecycle = MagicMock(spec=EmulatorLifecycle)
        lifecycle.destroy.side_effect = [RuntimeError("boom"), None]

        shutdown_all_instances(store, lifecycle)

        # Both instances should have had destroy attempted
        self.assertEqual(lifecycle.destroy.call_count, 2)

    def test_no_instances_is_noop(self):
        store = InstanceStore()
        lifecycle = MagicMock(spec=EmulatorLifecycle)

        shutdown_all_instances(store, lifecycle)

        lifecycle.destroy.assert_not_called()


class KillOrphanEmulatorsTest(unittest.TestCase):
    """Tests for kill_orphan_emulators."""

    @patch("instance_manager.src.cleanup.subprocess")
    def test_kills_orphan_emulator_processes(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="1234 emulator @vanpilot_pixel9pro_api36 -port 5554\n"
                   "5678 emulator @vanpilot_pixel9pro_api36 -port 5556\n",
        )

        kill_orphan_emulators()

        # Should have called pgrep, then kill for each PID
        calls = mock_subprocess.run.call_args_list
        pgrep_call = calls[0]
        self.assertIn("pgrep", pgrep_call.args[0])

        # Verify kill calls were made for both PIDs
        kill_pids = set()
        for c in calls[1:]:
            args = c.args[0]
            if args[0] == "kill" and args[1] == "-9":
                kill_pids.add(args[2])
        self.assertEqual(kill_pids, {"1234", "5678"})

    @patch("instance_manager.src.cleanup.subprocess")
    def test_no_orphans_found(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=1,  # pgrep returns 1 when no matches
            stdout="",
        )

        # Should not raise
        kill_orphan_emulators()

        # Only the pgrep call, no kills
        self.assertEqual(mock_subprocess.run.call_count, 1)

    @patch("instance_manager.src.cleanup.subprocess")
    def test_handles_pgrep_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = OSError("pgrep not found")

        # Should not raise
        kill_orphan_emulators()


if __name__ == "__main__":
    unittest.main()
