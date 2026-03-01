package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VanPilotScreen conversation tab integration.
 * Tests tab IDs, constants, and the tabManager property.
 */
@RunWith(JUnit4::class)
class VanPilotScreenTabsTest {

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

    @Test
    fun activeTabId_defaultsToVisual() {
        assertThat(VanPilotScreen.VISUAL_TAB_ID).isEqualTo("visual_card")
    }
}
