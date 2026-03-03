"""Tests for display profile wiring in emulator golden test (AC-10.2).

Verifies that the emulator golden test module reads DISPLAY_PROFILE
env var and selects the correct profile and golden directory.
"""

import os
import sys
import unittest
from unittest import mock

from goldens.display_profiles import DisplayProfile


class EmulatorGoldenDisplayProfileTest(unittest.TestCase):
    """Verify display profile wiring in emulator golden test."""

    def _load_module(self, profile_name=None):
        """Load test_emulator_golden with controlled env and mocked subprocess."""
        env = os.environ.copy()
        if profile_name:
            env["DISPLAY_PROFILE"] = profile_name
        else:
            env.pop("DISPLAY_PROFILE", None)

        # Clear cached module
        mods_to_remove = [k for k in sys.modules if "test_emulator_golden" in k]
        for k in mods_to_remove:
            del sys.modules[k]
        goldens_pkg = sys.modules.get("goldens")
        if goldens_pkg and hasattr(goldens_pkg, "test_emulator_golden"):
            delattr(goldens_pkg, "test_emulator_golden")

        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch(
                "subprocess.run",
                return_value=mock.Mock(stdout="", returncode=0),
            ),
            mock.patch("subprocess.Popen"),
        ):
            from goldens import test_emulator_golden as mod

            return mod

    def test_default_profile_when_no_env(self):
        """Without DISPLAY_PROFILE env, defaults to 'default' profile."""
        mod = self._load_module()
        self.assertIsInstance(mod.DISPLAY_PROFILE, DisplayProfile)
        self.assertEqual(mod.DISPLAY_PROFILE.name, "default")

    def test_default_golden_dir_uses_phase9(self):
        """Default profile golden dir ends with 'phase9'."""
        mod = self._load_module()
        self.assertTrue(mod.GOLDEN_DIR.endswith("phase9"))

    def test_13inch_profile_selected(self):
        """DISPLAY_PROFILE=13inch selects the 13-inch profile."""
        mod = self._load_module(profile_name="13inch")
        self.assertEqual(mod.DISPLAY_PROFILE.name, "13inch")
        self.assertEqual(mod.DISPLAY_PROFILE.dhu_width, 1920)
        self.assertEqual(mod.DISPLAY_PROFILE.dhu_height, 720)

    def test_13inch_golden_dir(self):
        """13-inch profile golden dir ends with '13inch'."""
        mod = self._load_module(profile_name="13inch")
        self.assertTrue(mod.GOLDEN_DIR.endswith("13inch"))

    def test_module_exports_display_profile(self):
        """Module must export DISPLAY_PROFILE."""
        mod = self._load_module()
        self.assertTrue(hasattr(mod, "DISPLAY_PROFILE"))


if __name__ == "__main__":
    unittest.main()
