"""Tests for standalone_client argument parsing, especially adb flag passthrough."""

import argparse
import os
import sys
import unittest

# The standalone_client module imports grpc and vendored proto stubs at module
# level.  We don't need those for argument-parsing tests, so mock them before
# the import.
from unittest import mock

sys.modules["grpc"] = mock.MagicMock()
sys.modules["instance_manager_pb2"] = mock.MagicMock()

from instance_manager.src.standalone_client import build_parser


class AdbArgParsingTest(unittest.TestCase):
    """Verify that the 'adb' subcommand correctly passes through flags."""

    def setUp(self):
        self.parser = build_parser()

    def test_basic_adb_command(self):
        args = self.parser.parse_args(["adb", "--name", "test", "ls", "/sdcard"])
        self.assertEqual(args.command, "adb")
        self.assertEqual(args.name, "test")
        self.assertEqual(args.shell_args, ["ls", "/sdcard"])

    def test_flags_passed_through(self):
        args = self.parser.parse_args(
            ["adb", "--name", "test", "am", "start", "-S", "com.vanpilot.auto"]
        )
        self.assertEqual(args.shell_args, ["am", "start", "-S", "com.vanpilot.auto"])

    def test_flags_with_separator(self):
        args = self.parser.parse_args(
            ["adb", "--name", "test", "--", "am", "start", "-n", "com.vanpilot.auto"]
        )
        # REMAINDER includes "--"; cmd_adb strips it at runtime
        shell_args = args.shell_args
        if shell_args and shell_args[0] == "--":
            shell_args = shell_args[1:]
        self.assertEqual(shell_args, ["am", "start", "-n", "com.vanpilot.auto"])

    def test_timeout_still_works(self):
        args = self.parser.parse_args(
            ["adb", "--name", "test", "--timeout", "60", "ls", "/sdcard"]
        )
        self.assertEqual(args.timeout, 60)
        self.assertEqual(args.shell_args, ["ls", "/sdcard"])

    def test_default_timeout(self):
        args = self.parser.parse_args(["adb", "--name", "test", "echo", "hi"])
        self.assertEqual(args.timeout, 30)


class OtherSubcommandsUnaffectedTest(unittest.TestCase):
    """Verify adb-push and adb-pull still work normally."""

    def setUp(self):
        self.parser = build_parser()

    def test_adb_push(self):
        args = self.parser.parse_args(
            ["adb-push", "--name", "test", "--file", "/tmp/a.txt", "--remote", "/sdcard/a.txt"]
        )
        self.assertEqual(args.command, "adb-push")
        self.assertEqual(args.file, "/tmp/a.txt")
        self.assertEqual(args.remote, "/sdcard/a.txt")

    def test_adb_pull(self):
        args = self.parser.parse_args(
            ["adb-pull", "--name", "test", "--remote", "/sdcard/b.txt", "--output", "/tmp/b.txt"]
        )
        self.assertEqual(args.command, "adb-pull")
        self.assertEqual(args.remote, "/sdcard/b.txt")
        self.assertEqual(args.output, "/tmp/b.txt")


if __name__ == "__main__":
    unittest.main()
