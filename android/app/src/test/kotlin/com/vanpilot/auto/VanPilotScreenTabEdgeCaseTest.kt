package com.vanpilot.auto

import androidx.car.app.model.ListTemplate
import androidx.car.app.navigation.model.NavigationTemplate
import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Edge-case tests for VanPilotScreen.selectTab() with invalid or
 * unusual tab IDs. Verifies graceful fallback to the visual tab
 * when the active tab ID is unrecognized, empty, or stale.
 *
 * See: https://github.com/widdowson/vanpilot/issues/33
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenTabEdgeCaseTest {

    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        screen = VanPilotScreen(carContext)
    }

    // =========================================================================
    // Unrecognized tab ID — falls back to visual tab
    // =========================================================================

    @Test
    fun selectTab_unrecognizedId_fallsBackToVisualTab() {
        screen.selectTab("totally_unknown_tab")

        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId)
            .isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
    }

    @Test
    fun selectTab_unrecognizedId_showsNavigationTemplate() {
        screen.selectTab("totally_unknown_tab")

        val template = screen.onGetTemplate()
        assertThat(template.tabContents!!.template)
            .isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun selectTab_unrecognizedId_updatesTabManagerState() {
        screen.selectTab("totally_unknown_tab")

        // selectTab still updates tabManager (it doesn't validate)
        assertThat(screen.tabManager.activeConversationTabId)
            .isEqualTo("totally_unknown_tab")
    }

    // =========================================================================
    // Empty string tab ID — falls back to visual tab
    // =========================================================================

    @Test
    fun selectTab_emptyString_fallsBackToVisualTab() {
        screen.selectTab("")

        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId)
            .isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
    }

    @Test
    fun selectTab_emptyString_showsNavigationTemplate() {
        screen.selectTab("")

        val template = screen.onGetTemplate()
        assertThat(template.tabContents!!.template)
            .isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun selectTab_emptyString_updatesTabManagerState() {
        screen.selectTab("")

        assertThat(screen.tabManager.activeConversationTabId).isEqualTo("")
    }

    // =========================================================================
    // selectTab called before onGetTemplate (invalidate before first render)
    // =========================================================================

    @Test
    fun selectTab_beforeOnGetTemplate_doesNotThrow() {
        // selectTab calls invalidate() internally. Verify this is safe
        // even before onGetTemplate has ever been called.
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)

        // If we reach here without exception, the test passes.
        assertThat(screen.tabManager.activeConversationTabId)
            .isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
    }

    @Test
    fun selectTab_beforeOnGetTemplate_subsequentRenderCorrect() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)

        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId)
            .isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
        assertThat(template.tabContents!!.template)
            .isInstanceOf(ListTemplate::class.java)
    }

    // =========================================================================
    // Tab selection after sub-agent is removed — falls back to visual tab
    // =========================================================================

    @Test
    fun selectTab_afterSubAgentRemoved_fallsBackToVisualTab() {
        val agentId = "researcher"
        val tabId = ConversationTabManager.subAgentTabId(agentId)

        // Select the sub-agent tab while it exists and verify it works
        screen.selectTab(tabId)
        val before = screen.onGetTemplate()
        assertThat(before.activeTabContentId).isEqualTo(tabId)

        // Remove the sub-agent, then re-render
        screen.tabManager.removeSubAgent(agentId)
        val after = screen.onGetTemplate()

        // Tab ID is now stale — falls back to visual
        assertThat(after.activeTabContentId)
            .isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
        assertThat(after.tabContents!!.template)
            .isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun selectTab_afterSubAgentRemoved_tabManagerStillTracksSelection() {
        val agentId = "researcher"
        val tabId = ConversationTabManager.subAgentTabId(agentId)

        screen.tabManager.removeSubAgent(agentId)
        screen.selectTab(tabId)

        // selectTab updates tabManager regardless of agent existence
        assertThat(screen.tabManager.activeConversationTabId).isEqualTo(tabId)
    }

    @Test
    fun selectTab_afterSubAgentRemoved_canSwitchBackToVisual() {
        val agentId = "coder"
        val tabId = ConversationTabManager.subAgentTabId(agentId)

        screen.selectTab(tabId)
        screen.tabManager.removeSubAgent(agentId)

        // Explicitly switch back to visual
        screen.selectTab(VanPilotScreen.VISUAL_TAB_ID)
        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId)
            .isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
        assertThat(screen.tabManager.activeConversationTabId).isNull()
    }
}
