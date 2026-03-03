"""Tests for display profile configuration (AC-10.2).

Verifies that display profiles are correctly defined for golden test
infrastructure, including the 13-inch automotive head unit profile.
"""

import unittest

from goldens.display_profiles import DisplayProfile, get_profile, list_profiles


class DisplayProfileDefaultTest(unittest.TestCase):
    """Verify the default display profile."""

    def test_default_profile_exists(self):
        profile = get_profile("default")
        self.assertIsInstance(profile, DisplayProfile)

    def test_default_profile_name(self):
        profile = get_profile("default")
        self.assertEqual(profile.name, "default")

    def test_default_profile_resolution(self):
        """Default profile uses 800x480 DHU resolution."""
        profile = get_profile("default")
        self.assertEqual(profile.dhu_width, 800)
        self.assertEqual(profile.dhu_height, 480)

    def test_default_profile_golden_dir(self):
        profile = get_profile("default")
        self.assertEqual(profile.golden_subdir, "phase9")


class DisplayProfile13InchTest(unittest.TestCase):
    """Verify the 13-inch automotive display profile (AC-10.2)."""

    def test_13inch_profile_exists(self):
        profile = get_profile("13inch")
        self.assertIsInstance(profile, DisplayProfile)

    def test_13inch_profile_name(self):
        profile = get_profile("13inch")
        self.assertEqual(profile.name, "13inch")

    def test_13inch_profile_resolution(self):
        """13-inch automotive display uses 1920x720 ultrawide."""
        profile = get_profile("13inch")
        self.assertEqual(profile.dhu_width, 1920)
        self.assertEqual(profile.dhu_height, 720)

    def test_13inch_profile_dpi(self):
        """13-inch at 1920x720 has approximately 160 DPI."""
        profile = get_profile("13inch")
        self.assertEqual(profile.dhu_dpi, 160)

    def test_13inch_profile_golden_dir(self):
        profile = get_profile("13inch")
        self.assertEqual(profile.golden_subdir, "13inch")

    def test_13inch_profile_dhu_resolution_string(self):
        """Profile should produce a DHU-compatible resolution string."""
        profile = get_profile("13inch")
        self.assertEqual(profile.dhu_resolution_arg, "1920x720")


class DisplayProfileLookupTest(unittest.TestCase):
    """Verify profile lookup behavior."""

    def test_unknown_profile_raises(self):
        with self.assertRaises(KeyError):
            get_profile("nonexistent")

    def test_list_profiles_includes_default(self):
        profiles = list_profiles()
        self.assertIn("default", profiles)

    def test_list_profiles_includes_13inch(self):
        profiles = list_profiles()
        self.assertIn("13inch", profiles)


if __name__ == "__main__":
    unittest.main()
