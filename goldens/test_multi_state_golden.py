"""Multi-state golden tests: one test per UI state from INVENTORY.md.

Each test captures a specific UI state and compares it against a committed
golden image. Tests are tagged "manual" and "exclusive" because they require
a running instance manager and emulator.

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to VanPilot APK (optional -- skips install if unset)
  GOLDEN_TOLERANCE: Per-channel pixel tolerance (default 5)

Usage:
  bazel test //goldens:visual_card_light_golden_test \\
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061 \\
    --test_env=VANPILOT_APK=bazel-bin/android/vanpilot.apk
"""

import os
import subprocess
import time
import unittest

from goldens.golden_test_harness import GoldenTestCase

GOLDEN_DIR = os.path.join(
    os.environ.get("TEST_SRCDIR", ""),
    os.environ.get("TEST_WORKSPACE", ""),
    "goldens",
    "captured",
)

TAB_SWITCH_SETTLE = 3  # seconds to wait after tab interaction


def _adb_shell(adb_port: int, *args: str, timeout: int = 15) -> str:
    """Run an ADB shell command."""
    serial = f"localhost:{adb_port}"
    result = subprocess.run(
        ["adb", "-s", serial, "shell", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


class VisualCardLightGoldenTest(GoldenTestCase):
    """Golden: Visual Card tab in light mode (default teal surface)."""

    instance_name = "golden-visual-light"

    def test_visual_card_light(self):
        golden_path = os.path.join(GOLDEN_DIR, "visual_card_light.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_visual_card_light.png", png)
        self.assert_matches_golden(png, golden_path)


class VisualCardDarkGoldenTest(GoldenTestCase):
    """Golden: Visual Card tab in dark mode (darker teal surface)."""

    instance_name = "golden-visual-dark"

    def test_visual_card_dark(self):
        # TODO: Send DHU "night" command to switch to dark mode
        golden_path = os.path.join(GOLDEN_DIR, "visual_card_dark.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_visual_card_dark.png", png)
        self.assert_matches_golden(png, golden_path)


class LeadAgentPopulatedGoldenTest(GoldenTestCase):
    """Golden: Lead Agent tab with mock conversation messages."""

    instance_name = "golden-lead-populated"

    def test_lead_agent_populated(self):
        # TODO: Tap Lead Agent tab (index 1) to switch
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "lead_agent_populated.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_lead_agent_populated.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentResearcherGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Researcher' tab with messages."""

    instance_name = "golden-sub-researcher"

    def test_sub_agent_researcher(self):
        # TODO: Tap sub-agent tab (index 2) to switch
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_researcher.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_researcher.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentCoderGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Coder' tab with messages."""

    instance_name = "golden-sub-coder"

    def test_sub_agent_coder(self):
        # TODO: Tap sub-agent tab (index 3) to switch
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_coder.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_coder.png", png)
        self.assert_matches_golden(png, golden_path)


class AllTabsOverviewGoldenTest(GoldenTestCase):
    """Golden: All 4 tabs visible with Visual tab selected."""

    instance_name = "golden-all-tabs"

    def test_all_tabs_visual_selected(self):
        golden_path = os.path.join(GOLDEN_DIR, "all_tabs_visual_selected.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_all_tabs_visual_selected.png", png)
        self.assert_matches_golden(png, golden_path)


class LeadAgentDarkGoldenTest(GoldenTestCase):
    """Golden: Lead Agent tab in dark mode."""

    instance_name = "golden-lead-dark"

    def test_lead_agent_dark(self):
        # TODO: Send DHU "night" command, then tap Lead Agent tab
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "lead_agent_dark.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_lead_agent_dark.png", png)
        self.assert_matches_golden(png, golden_path)


if __name__ == "__main__":
    unittest.main()
