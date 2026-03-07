"""Multi-state golden tests: one test per UI state from INVENTORY.md.

Each test captures a specific UI state and compares it against a committed
golden image. Tests are tagged "manual" and "exclusive" because they require
a running instance manager and emulator.

Env vars:
  INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
  VANPILOT_APK: Path to VanPilot APK (optional -- skips install if unset)
  GOLDEN_TOLERANCE: Per-channel pixel tolerance (default 5)

Usage:
  bazel test //goldens:visual_card_light_golden_test \
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061 \
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

# DHU tap coordinates for tabs (1920x1080 DHU coordinate space).
# These are the cropped coordinates (left=76, top=12) added back:
#   Visual:     ~229, 67
#   Lead Agent: ~374, 67
#   Researcher: ~516, 67
#   Coder:      ~661, 67
_TAB_VISUAL = (229, 67)
_TAB_LEAD_AGENT = (374, 67)
_TAB_RESEARCHER = (516, 67)
_TAB_CODER = (661, 67)


class VisualCardLightGoldenTest(GoldenTestCase):
    """Golden: Visual Card tab in light mode (default state after launch)."""

    instance_name = "golden-light-tabs"

    def test_visual_card_light(self):
        self.verify_vanpilot_foreground()
        golden_path = os.path.join(GOLDEN_DIR, "visual_card_light.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_visual_card_light.png", png)
        self.assert_matches_golden(png, golden_path)


class LeadAgentPopulatedGoldenTest(GoldenTestCase):
    """Golden: Lead Agent tab with conversation messages."""

    instance_name = "golden-light-tabs"

    def test_lead_agent_populated(self):
        self.verify_vanpilot_foreground()
        self.dhu_command(f"tap {_TAB_LEAD_AGENT[0]} {_TAB_LEAD_AGENT[1]}")
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "lead_agent_populated.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_lead_agent_populated.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentResearcherGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Researcher' tab with messages."""

    instance_name = "golden-light-tabs"

    def test_sub_agent_researcher(self):
        self.verify_vanpilot_foreground()
        self.dhu_command(f"tap {_TAB_RESEARCHER[0]} {_TAB_RESEARCHER[1]}")
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_researcher.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_researcher.png", png)
        self.assert_matches_golden(png, golden_path)


class SubAgentCoderGoldenTest(GoldenTestCase):
    """Golden: Sub-agent 'Coder' tab with messages."""

    instance_name = "golden-light-tabs"

    def test_sub_agent_coder(self):
        self.verify_vanpilot_foreground()
        self.dhu_command(f"tap {_TAB_CODER[0]} {_TAB_CODER[1]}")
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "sub_agent_coder.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_sub_agent_coder.png", png)
        self.assert_matches_golden(png, golden_path)


class VisualCardDarkGoldenTest(GoldenTestCase):
    """Golden: Visual Card tab in dark mode (darker teal surface)."""

    instance_name = "golden-dark-mode"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls._client:
            cls._client.dhu_command(cls.instance_name, "night on")
            time.sleep(TAB_SWITCH_SETTLE)

    @classmethod
    def tearDownClass(cls):
        if cls._client:
            try:
                cls._client.dhu_command(cls.instance_name, "night off")
            except Exception:
                pass
        super().tearDownClass()

    def test_visual_card_dark(self):
        self.verify_vanpilot_foreground()
        golden_path = os.path.join(GOLDEN_DIR, "visual_card_dark.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_visual_card_dark.png", png)
        self.assert_matches_golden(png, golden_path)


class LeadAgentDarkGoldenTest(GoldenTestCase):
    """Golden: Lead Agent tab in dark mode."""

    instance_name = "golden-dark-mode"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls._client:
            cls._client.dhu_command(cls.instance_name, "night on")
            time.sleep(TAB_SWITCH_SETTLE)

    @classmethod
    def tearDownClass(cls):
        if cls._client:
            try:
                cls._client.dhu_command(cls.instance_name, "night off")
            except Exception:
                pass
        super().tearDownClass()

    def test_lead_agent_dark(self):
        self.verify_vanpilot_foreground()
        self.dhu_command(f"tap {_TAB_LEAD_AGENT[0]} {_TAB_LEAD_AGENT[1]}")
        time.sleep(TAB_SWITCH_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "lead_agent_dark.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_lead_agent_dark.png", png)
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
#
# These are tracked in issue #155. When the harness gains state-driving
# capability, add tests with real goldens.
# Do NOT commit goldens that are identical to the default state under
# different names — that is dishonest and defeats the purpose of goldens.
# ============================================================================


if __name__ == "__main__":
    unittest.main()
