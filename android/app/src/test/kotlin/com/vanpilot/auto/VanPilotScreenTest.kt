package com.vanpilot.auto

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
    fun onGetTemplate_returnsNavigationTemplate() {
        val template = screen.onGetTemplate()
        assertThat(template).isInstanceOf(NavigationTemplate::class.java)
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
