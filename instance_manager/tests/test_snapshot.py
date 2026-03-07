"""Tests for emulator snapshot save/restore support."""

import unittest
from unittest.mock import MagicMock, patch
from concurrent import futures

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from instance_manager.src.emulator_lifecycle import (
    EmulatorLifecycle,
    SubprocessRunner,
)
from instance_manager.src.instance_manager_service import (
    add_instance_manager_service_to_server,
)
from instance_manager.src.instance_store import InstanceStore, RUNNING, CREATING
from instance_manager.src.port_allocator import PortAllocator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeSubprocessRunner(SubprocessRunner):
    """Records subprocess calls for verification."""

    def __init__(self):
        self.run_calls = []
        self.popen_calls = []
        self._boot_ready = True

    def run(self, args, **kwargs):
        self.run_calls.append((args, kwargs))
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        if "getprop" in args and "sys.boot_completed" in args:
            result.stdout = "1" if self._boot_ready else ""
        return result

    def popen(self, args, **kwargs):
        self.popen_calls.append((args, kwargs))
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.return_value = None
        proc.wait.return_value = 0
        return proc


# ---------------------------------------------------------------------------
# Lifecycle tests for save_snapshot
# ---------------------------------------------------------------------------

class SaveSnapshotLifecycleTest(unittest.TestCase):
    """Tests for EmulatorLifecycle.save_snapshot."""

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

    def test_save_snapshot_runs_adb_emu_command(self):
        """save_snapshot runs 'adb emu avd snapshot save <name>'."""
        store, runner, lifecycle = self._make_lifecycle()
        record = self._make_record(store)

        lifecycle.save_snapshot(record, "post_install")

        snapshot_calls = [
            c for c in runner.run_calls
            if "snapshot" in c[0] and "save" in c[0]
        ]
        self.assertEqual(len(snapshot_calls), 1)
        args = snapshot_calls[0][0]
        self.assertEqual(args[0], "adb")
        self.assertEqual(args[1], "-s")
        self.assertEqual(args[2], "emulator-5554")
        self.assertEqual(args[3], "emu")
        self.assertEqual(args[4], "avd")
        self.assertEqual(args[5], "snapshot")
        self.assertEqual(args[6], "save")
        self.assertEqual(args[7], "post_install")

    def test_save_snapshot_failure_raises(self):
        """save_snapshot raises RuntimeError when adb command fails."""

        class FailingSnapshotRunner(FakeSubprocessRunner):
            def run(self, args, **kwargs):
                result = super().run(args, **kwargs)
                if "snapshot" in args and "save" in args:
                    result.returncode = 1
                    result.stderr = "snapshot save failed"
                return result

        store, runner, lifecycle = self._make_lifecycle(runner=FailingSnapshotRunner())
        record = self._make_record(store)

        with self.assertRaises(RuntimeError) as ctx:
            lifecycle.save_snapshot(record, "bad_snapshot")
        self.assertIn("snapshot save failed", str(ctx.exception))


# ---------------------------------------------------------------------------
# gRPC service tests for SaveSnapshot RPC
# ---------------------------------------------------------------------------

class SaveSnapshotServiceTest(unittest.TestCase):
    """Tests for the SaveSnapshot RPC on InstanceManagerServicer."""

    def setUp(self):
        self.store = InstanceStore()
        self.port_allocator = PortAllocator(max_slots=4)
        self.lifecycle = MagicMock(spec=EmulatorLifecycle)

        def fake_create(name, avd_name, snapshot_name, headful, ports):
            self.store.update(name, state=RUNNING)
            return self.store.get(name)

        self.lifecycle.create.side_effect = fake_create
        self.lifecycle.screenshot.return_value = b"fake-png"
        self.lifecycle.emulator_screenshot_to_bytes.return_value = b"fake-emu-png"
        self.lifecycle.save_snapshot = MagicMock()

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        add_instance_manager_service_to_server(
            self.server, self.store, self.lifecycle, self.port_allocator,
        )
        port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(0)

    def _call(self, method, request):
        service = "vanpilot.v1.InstanceManagerService"
        resp_map = {
            "CreateInstance": instance_manager_pb2.CreateInstanceResponse,
            "SaveSnapshot": instance_manager_pb2.SaveSnapshotResponse,
            "InstallApk": instance_manager_pb2.InstallApkResponse,
        }
        resp_type = resp_map[method]
        return self.channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=type(request).SerializeToString,
            response_deserializer=resp_type.FromString,
        )(request)

    def _create_instance(self, name="snap-test"):
        return self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name=name),
        )

    def test_save_snapshot_success(self):
        """SaveSnapshot calls lifecycle.save_snapshot and returns instance info."""
        self._create_instance("snap-test")
        resp = self._call(
            "SaveSnapshot",
            instance_manager_pb2.SaveSnapshotRequest(
                name="snap-test", snapshot_name="post_install",
            ),
        )
        self.assertEqual(resp.instance.name, "snap-test")
        self.lifecycle.save_snapshot.assert_called_once()
        call_args = self.lifecycle.save_snapshot.call_args
        self.assertEqual(call_args[0][1], "post_install")

    def test_save_snapshot_nonexistent_instance(self):
        """SaveSnapshot returns NOT_FOUND for nonexistent instance."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "SaveSnapshot",
                instance_manager_pb2.SaveSnapshotRequest(
                    name="nope", snapshot_name="snap",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_save_snapshot_not_running(self):
        """SaveSnapshot returns FAILED_PRECONDITION if instance not running."""
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "SaveSnapshot",
                instance_manager_pb2.SaveSnapshotRequest(
                    name="creating", snapshot_name="snap",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_save_snapshot_empty_name_rejected(self):
        """SaveSnapshot rejects empty snapshot_name."""
        self._create_instance("snap-test")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "SaveSnapshot",
                instance_manager_pb2.SaveSnapshotRequest(
                    name="snap-test", snapshot_name="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_save_snapshot_invalid_name_rejected(self):
        """SaveSnapshot rejects snapshot names with invalid characters."""
        self._create_instance("snap-test2")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "SaveSnapshot",
                instance_manager_pb2.SaveSnapshotRequest(
                    name="snap-test2", snapshot_name="../evil",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_install_apk_with_save_snapshot(self):
        """InstallApk saves a snapshot when save_snapshot is set."""
        self.lifecycle.install_apk = MagicMock()
        def fake_restart(record):
            return self.store.get(record.name)
        self.lifecycle.restart_dhu = MagicMock(side_effect=fake_restart)

        self._create_instance("install-snap")
        resp = self._call(
            "InstallApk",
            instance_manager_pb2.InstallApkRequest(
                name="install-snap",
                apk_data=b"fake-apk",
                restart_dhu=True,
                save_snapshot="post_install_vanpilot",
            ),
        )
        self.assertEqual(resp.instance.name, "install-snap")
        self.lifecycle.install_apk.assert_called_once()
        self.lifecycle.restart_dhu.assert_called_once()
        self.lifecycle.save_snapshot.assert_called_once()
        call_args = self.lifecycle.save_snapshot.call_args
        self.assertEqual(call_args[0][1], "post_install_vanpilot")

    def test_install_apk_without_save_snapshot(self):
        """InstallApk does not save snapshot when save_snapshot is empty."""
        self.lifecycle.install_apk = MagicMock()
        self.lifecycle.restart_dhu = MagicMock()

        self._create_instance("no-snap")
        self._call(
            "InstallApk",
            instance_manager_pb2.InstallApkRequest(
                name="no-snap",
                apk_data=b"fake-apk",
                restart_dhu=False,
            ),
        )
        self.lifecycle.save_snapshot.assert_not_called()


# ---------------------------------------------------------------------------
# Lifecycle tests for load_snapshot
# ---------------------------------------------------------------------------

class LoadSnapshotLifecycleTest(unittest.TestCase):
    """Tests for EmulatorLifecycle.load_snapshot."""

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

    def test_load_snapshot_runs_adb_emu_command(self):
        """load_snapshot runs 'adb emu avd snapshot load <name>'."""
        store, runner, lifecycle = self._make_lifecycle()
        record = self._make_record(store)

        lifecycle.load_snapshot(record, "post_install")

        snapshot_calls = [
            c for c in runner.run_calls
            if "snapshot" in c[0] and "load" in c[0]
        ]
        self.assertEqual(len(snapshot_calls), 1)
        args = snapshot_calls[0][0]
        self.assertEqual(args, [
            "adb", "-s", "emulator-5554",
            "emu", "avd", "snapshot", "load", "post_install",
        ])

    def test_load_snapshot_failure_raises(self):
        """load_snapshot raises RuntimeError when adb command fails."""

        class FailingLoadRunner(FakeSubprocessRunner):
            def run(self, args, **kwargs):
                result = super().run(args, **kwargs)
                if "snapshot" in args and "load" in args:
                    result.returncode = 1
                    result.stderr = "snapshot load failed"
                return result

        store, runner, lifecycle = self._make_lifecycle(runner=FailingLoadRunner())
        record = self._make_record(store)

        with self.assertRaises(RuntimeError) as ctx:
            lifecycle.load_snapshot(record, "bad_snapshot")
        self.assertIn("snapshot load failed", str(ctx.exception))


# ---------------------------------------------------------------------------
# gRPC service tests for LoadSnapshot RPC
# ---------------------------------------------------------------------------

class LoadSnapshotServiceTest(unittest.TestCase):
    """Tests for the LoadSnapshot RPC on InstanceManagerServicer."""

    def setUp(self):
        self.store = InstanceStore()
        self.port_allocator = PortAllocator(max_slots=4)
        self.lifecycle = MagicMock(spec=EmulatorLifecycle)

        def fake_create(name, avd_name, snapshot_name, headful, ports):
            self.store.update(name, state=RUNNING)
            return self.store.get(name)

        self.lifecycle.create.side_effect = fake_create
        self.lifecycle.screenshot.return_value = b"fake-png"
        self.lifecycle.emulator_screenshot_to_bytes.return_value = b"fake-emu-png"
        self.lifecycle.load_snapshot = MagicMock()

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        add_instance_manager_service_to_server(
            self.server, self.store, self.lifecycle, self.port_allocator,
        )
        port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{port}")

    def tearDown(self):
        self.channel.close()
        self.server.stop(0)

    def _call(self, method, request):
        service = "vanpilot.v1.InstanceManagerService"
        resp_map = {
            "CreateInstance": instance_manager_pb2.CreateInstanceResponse,
            "LoadSnapshot": instance_manager_pb2.LoadSnapshotResponse,
        }
        resp_type = resp_map[method]
        return self.channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=type(request).SerializeToString,
            response_deserializer=resp_type.FromString,
        )(request)

    def _create_instance(self, name="load-test"):
        return self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name=name),
        )

    def test_load_snapshot_success(self):
        """LoadSnapshot calls lifecycle.load_snapshot and returns instance info."""
        self._create_instance("load-test")
        resp = self._call(
            "LoadSnapshot",
            instance_manager_pb2.LoadSnapshotRequest(
                name="load-test", snapshot_name="post_install",
            ),
        )
        self.assertEqual(resp.instance.name, "load-test")
        self.lifecycle.load_snapshot.assert_called_once()
        call_args = self.lifecycle.load_snapshot.call_args
        self.assertEqual(call_args[0][1], "post_install")

    def test_load_snapshot_nonexistent_instance(self):
        """LoadSnapshot returns NOT_FOUND for nonexistent instance."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "LoadSnapshot",
                instance_manager_pb2.LoadSnapshotRequest(
                    name="nope", snapshot_name="snap",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_load_snapshot_not_running(self):
        """LoadSnapshot returns FAILED_PRECONDITION if instance not running."""
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "LoadSnapshot",
                instance_manager_pb2.LoadSnapshotRequest(
                    name="creating", snapshot_name="snap",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_load_snapshot_empty_name_rejected(self):
        """LoadSnapshot rejects empty snapshot_name."""
        self._create_instance("load-test2")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "LoadSnapshot",
                instance_manager_pb2.LoadSnapshotRequest(
                    name="load-test2", snapshot_name="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_load_snapshot_invalid_name_rejected(self):
        """LoadSnapshot rejects snapshot names with invalid characters."""
        self._create_instance("load-test3")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "LoadSnapshot",
                instance_manager_pb2.LoadSnapshotRequest(
                    name="load-test3", snapshot_name="../evil",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)


if __name__ == "__main__":
    unittest.main()
