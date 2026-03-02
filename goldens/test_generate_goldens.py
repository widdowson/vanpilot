"""Unit tests for generate_goldens.py script logic."""

import os
import struct
import tempfile
import unittest

from unittest import mock

from goldens.generate_goldens import main
from mcp.src.png_util import make_teal_display, DISPLAY_WIDTH, DISPLAY_HEIGHT

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class GenerateGoldensOutputDirTest(unittest.TestCase):
    """Tests for output directory creation behavior."""

    def test_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            phase3_dir = os.path.join(tmpdir, "goldens", "phase3")
            self.assertTrue(os.path.isdir(phase3_dir))

    def test_succeeds_when_output_directory_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            phase3_dir = os.path.join(tmpdir, "goldens", "phase3")
            os.makedirs(phase3_dir)
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()  # Should not raise
            self.assertTrue(os.path.isdir(phase3_dir))


class GenerateGoldensWorkspaceResolutionTest(unittest.TestCase):
    """Tests for BUILD_WORKSPACE_DIRECTORY resolution."""

    def test_uses_build_workspace_directory_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            expected_path = os.path.join(
                tmpdir, "goldens", "phase3", "solid_color_surface.png"
            )
            self.assertTrue(os.path.exists(expected_path))

    def test_falls_back_to_cwd_when_env_unset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(
                os.environ, {}, clear=False
            ) as env, mock.patch("os.getcwd", return_value=tmpdir):
                env.pop("BUILD_WORKSPACE_DIRECTORY", None)
                main()
            expected_path = os.path.join(
                tmpdir, "goldens", "phase3", "solid_color_surface.png"
            )
            self.assertTrue(os.path.exists(expected_path))


class GenerateGoldensFileWriteTest(unittest.TestCase):
    """Tests for file writing and overwrite behavior."""

    def test_writes_valid_png_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            path = os.path.join(tmpdir, "goldens", "phase3", "solid_color_surface.png")
            with open(path, "rb") as f:
                header = f.read(8)
            self.assertEqual(header, PNG_SIGNATURE)

    def test_output_matches_make_teal_display(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            path = os.path.join(tmpdir, "goldens", "phase3", "solid_color_surface.png")
            with open(path, "rb") as f:
                actual = f.read()
            self.assertEqual(actual, make_teal_display())

    def test_output_has_correct_dimensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            path = os.path.join(tmpdir, "goldens", "phase3", "solid_color_surface.png")
            with open(path, "rb") as f:
                png = f.read()
            # IHDR data starts at offset 16 (8 sig + 4 len + 4 type)
            width, height = struct.unpack(">II", png[16:24])
            self.assertEqual(width, DISPLAY_WIDTH)
            self.assertEqual(height, DISPLAY_HEIGHT)

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            phase3_dir = os.path.join(tmpdir, "goldens", "phase3")
            os.makedirs(phase3_dir)
            path = os.path.join(phase3_dir, "solid_color_surface.png")
            # Write dummy content first
            with open(path, "wb") as f:
                f.write(b"old content")
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                main()
            with open(path, "rb") as f:
                actual = f.read()
            self.assertEqual(actual, make_teal_display())

    def test_prints_generated_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmpdir}):
                with mock.patch("builtins.print") as mock_print:
                    main()
            expected_path = os.path.join(
                tmpdir, "goldens", "phase3", "solid_color_surface.png"
            )
            mock_print.assert_called_once_with(f"Generated {expected_path}")


if __name__ == "__main__":
    unittest.main()
