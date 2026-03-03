"""Unit tests for the golden test harness.

Tests the InstanceManagerClient and GoldenTestCase with mocked gRPC.
These run without a real instance manager.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from goldens.golden_test_harness import (
    InstanceManagerClient,
    GoldenTestCase,
    INSTANCE_MANAGER_ADDR,
)


class InstanceManagerClientTest(unittest.TestCase):
    """Test the gRPC client wrapper."""

    @patch("goldens.golden_test_harness.grpc")
    def test_create_instance_calls_grpc(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel

        stub = MagicMock()
        channel.unary_unary.return_value = stub

        client = InstanceManagerClient("localhost:50061")
        client.create_instance("test-1")

        mock_grpc.insecure_channel.assert_called_once_with("localhost:50061")
        channel.unary_unary.assert_called_once()
        call_args = channel.unary_unary.call_args
        self.assertIn("CreateInstance", call_args[0][0])
        client.close()

    @patch("goldens.golden_test_harness.grpc")
    def test_destroy_instance_calls_grpc(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel
        channel.unary_unary.return_value = MagicMock()

        client = InstanceManagerClient()
        client.destroy_instance("test-1")

        channel.unary_unary.assert_called_once()
        call_args = channel.unary_unary.call_args
        self.assertIn("DestroyInstance", call_args[0][0])
        client.close()

    @patch("goldens.golden_test_harness.grpc")
    def test_screenshot_instance_calls_grpc(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel
        channel.unary_unary.return_value = MagicMock()

        client = InstanceManagerClient()
        client.screenshot_instance("test-1")

        channel.unary_unary.assert_called_once()
        call_args = channel.unary_unary.call_args
        self.assertIn("ScreenshotInstance", call_args[0][0])
        client.close()

    @patch("goldens.golden_test_harness.grpc")
    def test_get_instance_calls_grpc(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel
        channel.unary_unary.return_value = MagicMock()

        client = InstanceManagerClient()
        client.get_instance("test-1")

        channel.unary_unary.assert_called_once()
        call_args = channel.unary_unary.call_args
        self.assertIn("GetInstance", call_args[0][0])
        client.close()

    @patch("goldens.golden_test_harness.grpc")
    def test_default_addr(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel

        client = InstanceManagerClient()
        mock_grpc.insecure_channel.assert_called_once_with(INSTANCE_MANAGER_ADDR)
        client.close()

    @patch("goldens.golden_test_harness.grpc")
    def test_close_closes_channel(self, mock_grpc):
        channel = MagicMock()
        mock_grpc.insecure_channel.return_value = channel

        client = InstanceManagerClient()
        client.close()
        channel.close.assert_called_once()


class SaveTestOutputTest(unittest.TestCase):
    """Test the save_test_output helper."""

    def test_save_to_undeclared_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TEST_UNDECLARED_OUTPUTS_DIR": tmpdir}):
                tc = GoldenTestCase()
                path = tc.save_test_output("test.png", b"fake-png")
                self.assertIsNotNone(path)
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), b"fake-png")

    def test_returns_none_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("TEST_UNDECLARED_OUTPUTS_DIR", None)
            tc = GoldenTestCase()
            result = tc.save_test_output("test.png", b"fake-png")
            self.assertIsNone(result)


class AssertMatchesGoldenTest(unittest.TestCase):
    """Test the golden comparison assertion."""

    def test_skips_when_no_golden(self):
        tc = GoldenTestCase()
        tc._testMethodName = "test_skips_when_no_golden"
        with self.assertRaises(unittest.SkipTest):
            tc.assert_matches_golden(b"fake", "/nonexistent/golden.png")


if __name__ == "__main__":
    unittest.main()
