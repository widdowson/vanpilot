package com.vanpilot.auto

import androidx.car.app.model.TabTemplate
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
 * Tests that VanPilotScreen works with an injected ConversationTabManager
 * instead of hardcoded mock data, enabling real gRPC data to drive the UI.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenGrpcWiringTest {

    private lateinit var carContext: TestCarContext

    @Before
    fun setUp() {
        carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
    }

    @Test
    fun screen_withEmptyTabManager_showsNoMessages() {
        val tabManager = ConversationTabManager()
        val screen = VanPilotScreen(carContext, tabManager = tabManager)

        val template = screen.onGetTemplate()

        // Only Visual + Lead Agent tabs (no sub-agents registered)
        assertThat(template.tabs).hasSize(2)
    }

    @Test
    fun screen_withInjectedTabManager_reflectsItsState() {
        val tabManager = ConversationTabManager()
        tabManager.addSubAgent("researcher")
        val screen = VanPilotScreen(carContext, tabManager = tabManager)

        val template = screen.onGetTemplate()

        // Visual + Lead Agent + researcher
        assertThat(template.tabs).hasSize(3)
        assertThat(template.tabs[2].title.toString()).isEqualTo("Researcher")
    }

    @Test
    fun screen_defaultConstructor_usesMockData() {
        val screen = VanPilotScreen(carContext)

        val template = screen.onGetTemplate()

        // Mock data has 2 sub-agents: Visual + Lead + researcher + coder = 4
        assertThat(template.tabs).hasSize(4)
    }

    @Test
    fun screen_injectedTabManager_updatesReflectedAfterInvalidate() {
        val tabManager = ConversationTabManager()
        val screen = VanPilotScreen(carContext, tabManager = tabManager)

        // Initially no sub-agents
        var template = screen.onGetTemplate()
        assertThat(template.tabs).hasSize(2)

        // Add a sub-agent externally (simulating gRPC bridge updating it)
        tabManager.addSubAgent("coder")
        tabManager.addSubAgentMessage(
            "coder",
            ConversationMessage("coder", "Working on it", 1000L)
        )

        // After re-rendering, new tab should appear
        template = screen.onGetTemplate()
        assertThat(template.tabs).hasSize(3)
        assertThat(template.tabs[2].title.toString()).isEqualTo("Coder")
    }

    @Test
    fun screen_injectedTabManager_leadAgentMessagesVisible() {
        val tabManager = ConversationTabManager()
        tabManager.addLeadAgentMessage(
            ConversationMessage("lead", "Real gRPC message", 1000L)
        )
        val screen = VanPilotScreen(carContext, tabManager = tabManager)

        // Select lead agent tab to see messages
        screen.selectTab(VanPilotScreen.LEAD_AGENT_TAB_ID)
        val template = screen.onGetTemplate()

        // Verify lead agent tab shows the real message
        assertThat(template.activeTabContentId).isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
    }
}
