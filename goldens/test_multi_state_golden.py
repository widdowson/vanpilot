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


# ============================================================================
# Connection Indicator States
# ============================================================================

CONNECTION_SETTLE = 3  # seconds to wait after triggering state change


class ConnectionDisconnectedGoldenTest(GoldenTestCase):
    """Golden: Connection indicator in DISCONNECTED state (red icon).

    This is the default state — ConnectionMonitor starts as DISCONNECTED.
    No additional setup is needed beyond launching the app.
    """

    instance_name = "golden-conn-disconnected"

    def test_connection_disconnected(self):
        golden_path = os.path.join(GOLDEN_DIR, "connection_disconnected.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_connection_disconnected.png", png)
        self.assert_matches_golden(png, golden_path)


class ConnectionConnectedGoldenTest(GoldenTestCase):
    """Golden: Connection indicator in CONNECTED state (green icon).

    Requires a gRPC supervisor to be reachable so ConnectionMonitor
    transitions to CONNECTED after a successful RPC.
    """

    instance_name = "golden-conn-connected"

    def test_connection_connected(self):
        # TODO: Start a mock gRPC supervisor or send an ADB broadcast
        # to trigger ConnectionMonitor.onRpcSuccess() on the running app.
        time.sleep(CONNECTION_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "connection_connected.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_connection_connected.png", png)
        self.assert_matches_golden(png, golden_path)


class ConnectionReconnectingGoldenTest(GoldenTestCase):
    """Golden: Connection indicator in RECONNECTING state (yellow icon).

    Requires triggering the RECONNECTING transition: a prior connection
    must have failed and a reconnect attempt must be in progress.
    """

    instance_name = "golden-conn-reconnecting"

    def test_connection_reconnecting(self):
        # TODO: Trigger ConnectionMonitor.onReconnectAttempt() on the
        # running app via ADB broadcast or mock gRPC failure sequence.
        time.sleep(CONNECTION_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "connection_reconnecting.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_connection_reconnecting.png", png)
        self.assert_matches_golden(png, golden_path)


# ============================================================================
# History Navigation States
# ============================================================================

HISTORY_SETTLE = 3  # seconds to wait after triggering history changes


class HistoryInitialGoldenTest(GoldenTestCase):
    """Golden: History navigation with both back/forward disabled.

    This is the default state — no display history entries exist yet.
    """

    instance_name = "golden-history-initial"

    def test_history_initial(self):
        golden_path = os.path.join(GOLDEN_DIR, "history_initial.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_history_initial.png", png)
        self.assert_matches_golden(png, golden_path)


class HistoryBackEnabledGoldenTest(GoldenTestCase):
    """Golden: History navigation with back button enabled.

    Requires 2+ display entries so canGoBack() returns true.
    """

    instance_name = "golden-history-back"

    def test_history_back_enabled(self):
        # TODO: Send 2+ display_bitmap calls via gRPC to populate
        # DisplayHistory, enabling the back button.
        time.sleep(HISTORY_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "history_back_enabled.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_history_back_enabled.png", png)
        self.assert_matches_golden(png, golden_path)


class HistoryForwardEnabledGoldenTest(GoldenTestCase):
    """Golden: History navigation with forward button enabled.

    Requires 2+ display entries followed by a goBack(), so
    canGoForward() returns true.
    """

    instance_name = "golden-history-forward"

    def test_history_forward_enabled(self):
        # TODO: Send 2+ display_bitmap calls via gRPC, then trigger
        # a back navigation to enable the forward button.
        time.sleep(HISTORY_SETTLE)
        golden_path = os.path.join(GOLDEN_DIR, "history_forward_enabled.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_history_forward_enabled.png", png)
        self.assert_matches_golden(png, golden_path)


# ============================================================================
# Combined Action Strip State
# ============================================================================


class FullActionStripGoldenTest(GoldenTestCase):
    """Golden: Full action strip with all 4 buttons visible.

    The Visual tab action strip contains:
      1. Connection indicator (tinted icon)
      2. PAN action
      3. Back history button (arrow left)
      4. Forward history button (arrow right)

    This captures the default state where connection is DISCONNECTED
    (red indicator) and both history buttons are disabled.
    """

    instance_name = "golden-full-actionstrip"

    def test_full_action_strip(self):
        golden_path = os.path.join(GOLDEN_DIR, "full_action_strip.png")
        png = self.capture_dhu_screenshot()
        self.save_test_output("actual_full_action_strip.png", png)
        self.assert_matches_golden(png, golden_path)


if __name__ == "__main__":
    unittest.main()
