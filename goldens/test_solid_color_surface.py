"""Golden test for the Phase 3 solid color surface."""

import os
import struct
import unittest

from mcp.src.png_util import make_teal_display

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Bazel makes data deps available via runfiles — resolve relative to the
# test script's directory, which Bazel sets as the workspace root.
_GOLDEN_PATH = os.path.join(
    os.environ.get("TEST_SRCDIR", ""),
    os.environ.get("TEST_WORKSPACE", ""),
    "goldens",
    "phase3",
    "solid_color_surface.png",
)


class SolidColorSurfaceGoldenTest(unittest.TestCase):
    """Verify the committed golden matches make_teal_display() output."""

    def test_golden_file_exists(self):
        self.assertTrue(
            os.path.exists(_GOLDEN_PATH),
            f"Golden file not found at {_GOLDEN_PATH}",
        )

    def test_golden_has_png_signature(self):
        with open(_GOLDEN_PATH, "rb") as f:
            header = f.read(8)
        self.assertEqual(header, PNG_SIGNATURE)

    def test_golden_reasonable_size(self):
        size = os.path.getsize(_GOLDEN_PATH)
        self.assertGreater(size, 1024, "Golden PNG is suspiciously small")
        self.assertLess(size, 50 * 1024, "Golden PNG is suspiciously large")

    def test_golden_matches_make_teal_display(self):
        expected = make_teal_display()
        with open(_GOLDEN_PATH, "rb") as f:
            actual = f.read()
        if actual != expected:
            # Write actual output for CI artifact comparison
            undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
            if undeclared:
                os.makedirs(undeclared, exist_ok=True)
                diff_path = os.path.join(undeclared, "solid_color_surface_actual.png")
                with open(diff_path, "wb") as f:
                    f.write(expected)
        self.assertEqual(actual, expected, "Golden image does not match make_teal_display() output")


if __name__ == "__main__":
    unittest.main()
