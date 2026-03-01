"""Smoke test: verify Python proto codegen produces importable modules."""

import unittest

from proto.vanpilot.v1 import sync_pb2
from proto.vanpilot.v1 import display_pb2
from proto.vanpilot.v1 import screenshot_pb2


class CodegenTest(unittest.TestCase):

    def test_sync_pb2_imports(self):
        self.assertTrue(hasattr(sync_pb2, "DESCRIPTOR"))

    def test_display_pb2_imports(self):
        self.assertTrue(hasattr(display_pb2, "DESCRIPTOR"))

    def test_screenshot_pb2_imports(self):
        self.assertTrue(hasattr(screenshot_pb2, "DESCRIPTOR"))


if __name__ == "__main__":
    unittest.main()
