"""Tests for environment-based server configuration."""

import os
import unittest
from unittest.mock import patch

from supervisor.src.server import parse_server_config


class ParseServerConfigTest(unittest.TestCase):
    """Tests that parse_server_config reads environment variables with correct defaults."""

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_when_no_env_vars(self):
        """Without env vars, defaults are [::]:50051 and localhost:50052."""
        host, port, app_target = parse_server_config()
        self.assertEqual(host, "[::]")
        self.assertEqual(port, 50051)
        self.assertEqual(app_target, "localhost:50052")

    @patch.dict(os.environ, {"GRPC_PORT": "9999"})
    def test_reads_grpc_port(self):
        host, port, app_target = parse_server_config()
        self.assertEqual(port, 9999)

    @patch.dict(os.environ, {"GRPC_HOST": "0.0.0.0"})
    def test_reads_grpc_host(self):
        host, port, app_target = parse_server_config()
        self.assertEqual(host, "0.0.0.0")

    @patch.dict(os.environ, {"GRPC_APP_TARGET": "pixel.tailnet:50052"})
    def test_reads_grpc_app_target(self):
        host, port, app_target = parse_server_config()
        self.assertEqual(app_target, "pixel.tailnet:50052")

    @patch.dict(os.environ, {
        "GRPC_HOST": "0.0.0.0",
        "GRPC_PORT": "8080",
        "GRPC_APP_TARGET": "10.0.0.5:50052",
    })
    def test_reads_all_env_vars(self):
        host, port, app_target = parse_server_config()
        self.assertEqual(host, "0.0.0.0")
        self.assertEqual(port, 8080)
        self.assertEqual(app_target, "10.0.0.5:50052")

    @patch.dict(os.environ, {"GRPC_PORT": "not_a_number"})
    def test_invalid_port_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_server_config()


if __name__ == "__main__":
    unittest.main()
