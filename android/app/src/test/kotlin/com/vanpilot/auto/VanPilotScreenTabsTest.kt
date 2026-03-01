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
 * Behavioral tests for VanPilotScreen conversation tab switching.
 * Verifies selectTab triggers correct state changes.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenTabsTest {

    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        screen = VanPilotScreen(carContext)
    }

    // =========================================================================
    // Constants
    // =========================================================================

    @Test
    fun leadAgentTabId_constant() {
        assertThat(VanPilotScreen.LEAD_AGENT_TAB_ID).isEqualTo("lead_agent")
    }

    @Test
    fun visualTabId_unchanged() {
        assertThat(VanPilotScreen.VISUAL_TAB_ID).isEqualTo("visual_card")
    }

    @Test
    fun tabIds_areDistinct() {
        val ids = setOf(
            VanPilotScreen.VISUAL_TAB_ID,
            VanPilotScreen.LEAD_AGENT_TAB_ID
        )
        assertThat(ids).hasSize(2)
    }

    // =========================================================================
    // Default state
    // =========================================================================

    @Test
    fun defaultActiveTab_isVisual() {
        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId).isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
    }

    @Test
    fun defaultTabContents_isNavigationTemplate() {
        val template = screen.onGetTemplate()
        assertThat(template.tabContents!!.template)
            .isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun defaultConversationTabId_isNull() {
        assertThat(screen.tabManager.activeConversationTabId).isNull()
    }

    // =========================================================================
    // Tab switching behavior
    // =========================================================================

    @Test
    fun selectLeadAgentTab_updatesActiveTab() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)

        val updated = screen.onGetTemplate()
        assertThat(updated.activeTabContentId)
            .isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
    }

    @Test
    fun selectLeadAgentTab_showsListTemplate() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)

        val updated = screen.onGetTemplate()
        assertThat(updated.tabContents!!.template)
            .isInstanceOf(ListTemplate::class.java)
    }

    @Test
    fun selectLeadAgentTab_updatesTabManager() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)

        assertThat(screen.tabManager.activeConversationTabId)
            .isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
    }

    @Test
    fun selectSubAgentTab_updatesActiveTab() {
        val subAgentTabId = ConversationTabManager.subAgentTabId("researcher")
        screen.selectTab(subAgentTabId)

        val updated = screen.onGetTemplate()
        assertThat(updated.activeTabContentId).isEqualTo(subAgentTabId)
    }

    @Test
    fun selectSubAgentTab_showsListTemplate() {
        val subAgentTabId = ConversationTabManager.subAgentTabId("researcher")
        screen.selectTab(subAgentTabId)

        val updated = screen.onGetTemplate()
        assertThat(updated.tabContents!!.template)
            .isInstanceOf(ListTemplate::class.java)
    }

    @Test
    fun selectSubAgentTab_updatesTabManager() {
        val subAgentTabId = ConversationTabManager.subAgentTabId("researcher")
        screen.selectTab(subAgentTabId)

        assertThat(screen.tabManager.activeConversationTabId)
            .isEqualTo(subAgentTabId)
    }

    @Test
    fun switchBackToVisual_restoresNavigationTemplate() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)
        screen.selectTab(VanPilotScreen.VISUAL_TAB_ID)

        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId)
            .isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
        assertThat(template.tabContents!!.template)
            .isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun switchBackToVisual_clearsConversationTabId() {
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)
        assertThat(screen.tabManager.activeConversationTabId).isNotNull()

        screen.selectTab(VanPilotScreen.VISUAL_TAB_ID)
        assertThat(screen.tabManager.activeConversationTabId).isNull()
    }
}
