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


class VisualCardLightGoldenTest(GoldenTestCase):
    """Golden: Visual Card tab in light mode (default state after launch)."""

    instance_name = "golden-visual-light"

    def test_visual_card_light(self):
        golden_path = os.path.join(GOLDEN_DIR, "visual_card_light.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_visual_card_light.png", png)
        self.assert_matches_golden(png, golden_path)


class LeadAgentPopulatedGoldenTest(GoldenTestCase):
    """Golden: Lead Agent tab with conversation messages."""

    instance_name = "golden-lead-populated"

    def test_lead_agent_populated(self):
        # TODO: Tap Lead Agent tab via DHU command (see #155)
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "lead_agent_populated.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_lead_agent_populated.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentResearcherGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Researcher' tab with messages."""

    instance_name = "golden-sub-researcher"

    def test_sub_agent_researcher(self):
        # TODO: Tap Researcher tab via DHU command (see #155)
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_researcher.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_researcher.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentCoderGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Coder' tab with messages."""

    instance_name = "golden-sub-coder"

    def test_sub_agent_coder(self):
        # TODO: Tap Coder tab via DHU command (see #155)
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_coder.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_coder.png", png)
        self.assert_matches_golden(png, golden_path)


# ============================================================================
# States not yet drivable programmatically
# ============================================================================
#
# The following states require infrastructure that doesn't exist yet:
#   - Connection indicator states (CONNECTED, RECONNECTING) need a mock
#     gRPC supervisor or ADB broadcast to trigger ConnectionMonitor
#   - History navigation states (back enabled, forward enabled) need
#     display_bitmap calls via gRPC to populate DisplayHistory
#   - Dark mode needs DHU "night" command support in the test harness
#
# These are tracked in issue #155. When the harness gains DHU command
# support and state-driving capability, add tests with real goldens.
# Do NOT commit goldens that are identical to the default state under
# different names — that is dishonest and defeats the purpose of goldens.
# ============================================================================


if __name__ == "__main__":
    unittest.main()
