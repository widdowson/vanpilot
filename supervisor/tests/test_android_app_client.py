"""Tests for the AndroidAppClient (supervisor -> Android app reverse gRPC)."""

import unittest
from concurrent import futures

import grpc

from proto.vanpilot.v1 import screenshot_pb2
from supervisor.src.android_app_client import AndroidAppClient


class _FakeAndroidAppServicer:
    """Fake implementation of AndroidAppService for testing."""

    def __init__(self):
        self.current_cache_key = ""
        self.screenshot_data = b""
        self.cache_keys = set()

    def GetCurrentDisplay(self, request, context):
        return screenshot_pb2.GetCurrentDisplayResponse(
            current_cache_key=self.current_cache_key,
        )

    def RequestScreenshot(self, request, context):
        return screenshot_pb2.RequestScreenshotResponse(
            screenshot=self.screenshot_data,
        )

    def QueryCache(self, request, context):
        requested = list(request.keys)
        if not requested:
            return screenshot_pb2.QueryCacheResponse(
                present_keys=sorted(self.cache_keys),
            )
        present = [k for k in requested if k in self.cache_keys]
        missing = [k for k in requested if k not in self.cache_keys]
        return screenshot_pb2.QueryCacheResponse(
            present_keys=present,
            missing_keys=missing,
        )


class _FakeAndroidAppGenericHandler(grpc.GenericRpcHandler):
    """Maps AndroidAppService method paths to fake handler functions."""

    def __init__(self, servicer):
        self._handlers = {
            "/vanpilot.v1.AndroidAppService/GetCurrentDisplay": grpc.unary_unary_rpc_method_handler(
                servicer.GetCurrentDisplay,
                request_deserializer=screenshot_pb2.GetCurrentDisplayRequest.FromString,
                response_serializer=screenshot_pb2.GetCurrentDisplayResponse.SerializeToString,
            ),
            "/vanpilot.v1.AndroidAppService/RequestScreenshot": grpc.unary_unary_rpc_method_handler(
                servicer.RequestScreenshot,
                request_deserializer=screenshot_pb2.RequestScreenshotRequest.FromString,
                response_serializer=screenshot_pb2.RequestScreenshotResponse.SerializeToString,
            ),
            "/vanpilot.v1.AndroidAppService/QueryCache": grpc.unary_unary_rpc_method_handler(
                servicer.QueryCache,
                request_deserializer=screenshot_pb2.QueryCacheRequest.FromString,
                response_serializer=screenshot_pb2.QueryCacheResponse.SerializeToString,
            ),
        }

    def service(self, handler_call_details):
        return self._handlers.get(handler_call_details.method)


class AndroidAppClientGetCurrentDisplayTest(unittest.TestCase):
    """Tests for AndroidAppClient.get_current_display()."""

    def setUp(self):
        self.servicer = _FakeAndroidAppServicer()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        self.server.add_generic_rpc_handlers(
            [_FakeAndroidAppGenericHandler(self.servicer)]
        )
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")
        self.client = AndroidAppClient(self.channel)

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def test_returns_empty_when_nothing_displayed(self):
        self.servicer.current_cache_key = ""
        result = self.client.get_current_display()
        self.assertEqual(result, "")

    def test_returns_cache_key_when_displaying(self):
        self.servicer.current_cache_key = "0xDEADBEEF"
        result = self.client.get_current_display()
        self.assertEqual(result, "0xDEADBEEF")


class AndroidAppClientRequestScreenshotTest(unittest.TestCase):
    """Tests for AndroidAppClient.request_screenshot()."""

    def setUp(self):
        self.servicer = _FakeAndroidAppServicer()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        self.server.add_generic_rpc_handlers(
            [_FakeAndroidAppGenericHandler(self.servicer)]
        )
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")
        self.client = AndroidAppClient(self.channel)

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def test_returns_empty_bytes_when_no_screenshot(self):
        self.servicer.screenshot_data = b""
        result = self.client.request_screenshot()
        self.assertEqual(result, b"")

    def test_returns_png_data(self):
        png_header = b"\x89PNG\r\n\x1a\n"
        self.servicer.screenshot_data = png_header
        result = self.client.request_screenshot()
        self.assertEqual(result, png_header)

    def test_returns_large_screenshot(self):
        large_data = b"\x89PNG" + b"\x00" * 100000
        self.servicer.screenshot_data = large_data
        result = self.client.request_screenshot()
        self.assertEqual(result, large_data)


class AndroidAppClientQueryCacheTest(unittest.TestCase):
    """Tests for AndroidAppClient.query_cache()."""

    def setUp(self):
        self.servicer = _FakeAndroidAppServicer()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        self.server.add_generic_rpc_handlers(
            [_FakeAndroidAppGenericHandler(self.servicer)]
        )
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel(f"localhost:{self.port}")
        self.client = AndroidAppClient(self.channel)

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def test_returns_all_keys_when_no_query(self):
        self.servicer.cache_keys = {"a", "b", "c"}
        present, missing = self.client.query_cache()
        self.assertCountEqual(present, ["a", "b", "c"])
        self.assertEqual(missing, [])

    def test_partitions_specific_keys(self):
        self.servicer.cache_keys = {"a", "c"}
        present, missing = self.client.query_cache(["a", "b", "c"])
        self.assertCountEqual(present, ["a", "c"])
        self.assertCountEqual(missing, ["b"])

    def test_all_missing(self):
        self.servicer.cache_keys = set()
        present, missing = self.client.query_cache(["x", "y"])
        self.assertEqual(present, [])
        self.assertCountEqual(missing, ["x", "y"])

    def test_empty_cache_empty_query(self):
        self.servicer.cache_keys = set()
        present, missing = self.client.query_cache()
        self.assertEqual(present, [])
        self.assertEqual(missing, [])

    def test_all_present(self):
        self.servicer.cache_keys = {"x", "y", "z"}
        present, missing = self.client.query_cache(["x", "y", "z"])
        self.assertCountEqual(present, ["x", "y", "z"])
        self.assertEqual(missing, [])


class AndroidAppClientConnectionErrorTest(unittest.TestCase):
    """Tests that the client raises on connection failure."""

    def test_raises_on_unreachable_server(self):
        channel = grpc.insecure_channel("localhost:1")
        client = AndroidAppClient(channel)
        with self.assertRaises(grpc.RpcError):
            client.get_current_display()
        channel.close()


if __name__ == "__main__":
    unittest.main()
