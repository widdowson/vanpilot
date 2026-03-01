package com.vanpilot.auto

import androidx.car.app.model.Action
import androidx.car.app.model.TabTemplate
import androidx.car.app.navigation.model.NavigationTemplate
import androidx.car.app.testing.ScreenController
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
 * Behavioral tests for VanPilotScreen.
 * Uses ScreenController from the Car App Library testing framework.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenTest {

    private lateinit var screen: VanPilotScreen
    private lateinit var controller: ScreenController

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        screen = VanPilotScreen(carContext)
        controller = ScreenController(screen)
    }

    @Test
    fun onGetTemplate_returnsTabTemplate() {
        val template = screen.onGetTemplate()
        assertThat(template).isInstanceOf(TabTemplate::class.java)
    }

    @Test
    fun onGetTemplate_hasFourTabs() {
        val template = screen.onGetTemplate()
        // Visual + Lead Agent + 2 sub-agents from mock data
        assertThat(template.tabs).hasSize(4)
    }

    @Test
    fun onGetTemplate_firstTabTitleIsVisual() {
        val template = screen.onGetTemplate()
        assertThat(template.tabs[0].title.toString()).isEqualTo("Visual")
    }

    @Test
    fun onGetTemplate_secondTabTitleIsLeadAgent() {
        val template = screen.onGetTemplate()
        assertThat(template.tabs[1].title.toString()).isEqualTo("Lead Agent")
    }

    @Test
    fun onGetTemplate_visualTabContentIdMatchesConstant() {
        val template = screen.onGetTemplate()
        assertThat(template.tabs[0].contentId).isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
    }

    @Test
    fun onGetTemplate_leadAgentTabContentIdMatchesConstant() {
        val template = screen.onGetTemplate()
        assertThat(template.tabs[1].contentId).isEqualTo(VanPilotScreen.LEAD_AGENT_TAB_ID)
    }

    @Test
    fun onGetTemplate_activeTabIsVisualCard() {
        val template = screen.onGetTemplate()
        assertThat(template.activeTabContentId).isEqualTo(VanPilotScreen.VISUAL_TAB_ID)
    }

    @Test
    fun onGetTemplate_tabContentsHasNavigationTemplate() {
        val template = screen.onGetTemplate()
        val contents = template.tabContents
        assertThat(contents).isNotNull()
        assertThat(contents!!.template).isInstanceOf(NavigationTemplate::class.java)
    }

    @Test
    fun surfaceCallback_isInitialized() {
        assertThat(screen.surfaceCallback).isNotNull()
        assertThat(screen.surfaceCallback).isInstanceOf(VanPilotSurfaceCallback::class.java)
    }

    @Test
    fun visualTabIdConstant_isCorrect() {
        assertThat(VanPilotScreen.VISUAL_TAB_ID).isEqualTo("visual_card")
    }

    @Test
    fun leadAgentTabIdConstant_isCorrect() {
        assertThat(VanPilotScreen.LEAD_AGENT_TAB_ID).isEqualTo("lead_agent")
    }
}
