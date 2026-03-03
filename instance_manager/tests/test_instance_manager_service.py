"""Tests for InstanceManagerServicer with in-process gRPC."""

import unittest
from concurrent import futures
from unittest.mock import MagicMock, patch

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

from instance_manager.src.emulator_lifecycle import EmulatorLifecycle
from instance_manager.src.instance_manager_service import (
    add_instance_manager_service_to_server,
)
from instance_manager.src.instance_store import InstanceStore, RUNNING, CREATING
from instance_manager.src.port_allocator import PortAllocator


class InstanceManagerServiceTest(unittest.TestCase):

    def setUp(self):
        self.store = InstanceStore()
        self.port_allocator = PortAllocator(max_slots=4)
        self.lifecycle = MagicMock(spec=EmulatorLifecycle)

        # Make lifecycle.create return a record with RUNNING state
        def fake_create(name, avd_name, snapshot_name, headful, ports):
            self.store.update(name, state=RUNNING)
            return self.store.get(name)

        self.lifecycle.create.side_effect = fake_create
        self.lifecycle.screenshot.return_value = b"fake-png-bytes"
        self.lifecycle.emulator_screenshot_to_bytes.return_value = b"fake-emu-png"

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
        """Invoke an RPC using the channel directly."""
        service = "vanpilot.v1.InstanceManagerService"
        req_type = type(request)
        resp_map = {
            "CreateInstance": instance_manager_pb2.CreateInstanceResponse,
            "DestroyInstance": instance_manager_pb2.DestroyInstanceResponse,
            "ListInstances": instance_manager_pb2.ListInstancesResponse,
            "GetInstance": instance_manager_pb2.GetInstanceResponse,
            "ScreenshotInstance": instance_manager_pb2.ScreenshotInstanceResponse,
            "RestartDhu": instance_manager_pb2.RestartDhuResponse,
            "DhuCommand": instance_manager_pb2.DhuCommandResponse,
        }
        resp_type = resp_map[method]
        return self.channel.unary_unary(
            f"/{service}/{method}",
            request_serializer=req_type.SerializeToString,
            response_deserializer=resp_type.FromString,
        )(request)

    def test_create_instance_with_defaults(self):
        resp = self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="agent-1"),
        )
        self.assertEqual(resp.instance.name, "agent-1")
        self.assertEqual(resp.instance.state, RUNNING)
        self.assertEqual(resp.instance.emulator_console_port, 5554)
        self.lifecycle.create.assert_called_once()
        call_kwargs = self.lifecycle.create.call_args
        self.assertEqual(call_kwargs.kwargs.get("avd_name") or call_kwargs[1].get("avd_name", call_kwargs[0][1]),
                         "vanpilot_pixel9pro_api36")

    def test_create_instance_duplicate_name(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="dup"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "CreateInstance",
                instance_manager_pb2.CreateInstanceRequest(name="dup"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.ALREADY_EXISTS)

    def test_destroy_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="to-destroy"),
        )
        self._call(
            "DestroyInstance",
            instance_manager_pb2.DestroyInstanceRequest(name="to-destroy"),
        )
        self.lifecycle.destroy.assert_called_once()
        # Should be gone from store
        resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(resp.instances), 0)

    def test_destroy_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DestroyInstance",
                instance_manager_pb2.DestroyInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_list_instances(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="a"),
        )
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="b"),
        )
        resp = self._call(
            "ListInstances",
            instance_manager_pb2.ListInstancesRequest(),
        )
        self.assertEqual(len(resp.instances), 2)
        names = {i.name for i in resp.instances}
        self.assertEqual(names, {"a", "b"})

    def test_get_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="test"),
        )
        resp = self._call(
            "GetInstance",
            instance_manager_pb2.GetInstanceRequest(name="test"),
        )
        self.assertEqual(resp.instance.name, "test")

    def test_get_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "GetInstance",
                instance_manager_pb2.GetInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_screenshot_instance(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="snap"),
        )
        resp = self._call(
            "ScreenshotInstance",
            instance_manager_pb2.ScreenshotInstanceRequest(name="snap"),
        )
        self.assertEqual(resp.dhu_screenshot_png, b"fake-png-bytes")
        self.assertEqual(resp.emulator_screenshot_png, b"fake-emu-png")
        self.assertGreater(resp.captured_at_ms, 0)

    def test_screenshot_not_running(self):
        # Create an instance but leave it in CREATING state
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "ScreenshotInstance",
                instance_manager_pb2.ScreenshotInstanceRequest(name="creating"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_screenshot_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "ScreenshotInstance",
                instance_manager_pb2.ScreenshotInstanceRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_restart_dhu(self):
        # Set up restart_dhu mock to return the updated record
        def fake_restart_dhu(record):
            return self.store.get(record.name)

        self.lifecycle.restart_dhu = MagicMock(side_effect=fake_restart_dhu)

        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="restart-test"),
        )
        resp = self._call(
            "RestartDhu",
            instance_manager_pb2.RestartDhuRequest(name="restart-test"),
        )
        self.assertEqual(resp.instance.name, "restart-test")
        self.lifecycle.restart_dhu.assert_called_once()

    def test_restart_dhu_not_running(self):
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "RestartDhu",
                instance_manager_pb2.RestartDhuRequest(name="creating"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_restart_dhu_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "RestartDhu",
                instance_manager_pb2.RestartDhuRequest(name="nope"),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_dhu_command(self):
        self.lifecycle.dhu_command = MagicMock(return_value=b"")
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="cmd-test"),
        )
        resp = self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="cmd-test", command="keycode home",
            ),
        )
        self.assertGreater(resp.executed_at_ms, 0)
        self.lifecycle.dhu_command.assert_called_once()

    def test_dhu_command_screenshot_updates_store(self):
        self.lifecycle.dhu_command = MagicMock(return_value=b"fresh-png")
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="cache-test"),
        )
        self._call(
            "DhuCommand",
            instance_manager_pb2.DhuCommandRequest(
                name="cache-test", command="tap 100 200",
                capture_screenshot=True,
            ),
        )
        record = self.store.get("cache-test")
        self.assertEqual(record.last_screenshot_png, b"fresh-png")
        self.assertIsNotNone(record.last_screenshot_at_ms)

    def test_dhu_command_not_running(self):
        self.store.create("creating", 5554, 5555, 5277, False, 1000, "avd")
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="creating", command="keycode home",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_dhu_command_nonexistent(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="nope", command="keycode home",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_dhu_command_empty_command(self):
        self._call(
            "CreateInstance",
            instance_manager_pb2.CreateInstanceRequest(name="empty-cmd"),
        )
        with self.assertRaises(grpc.RpcError) as ctx:
            self._call(
                "DhuCommand",
                instance_manager_pb2.DhuCommandRequest(
                    name="empty-cmd", command="",
                ),
            )
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)


if __name__ == "__main__":
    unittest.main()
