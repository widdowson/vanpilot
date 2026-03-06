package com.vanpilot.auto

import androidx.car.app.model.Action
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

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenHistoryTest {

    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        screen = VanPilotScreen(carContext)
    }

    @Test
    fun visualTab_actionStripContainsPan() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        assertThat(actions).contains(Action.PAN)
    }

    @Test
    fun visualTab_actionStripHasThreeActions() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        // PAN + back + forward
        assertThat(actions).hasSize(3)
    }

    @Test
    fun visualTab_backButtonDisabledInitially() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        val backAction = actions.first { it.title?.toString() == "\u2190" }
        assertThat(backAction.isEnabled).isFalse()
    }

    @Test
    fun visualTab_forwardButtonDisabledInitially() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        val forwardAction = actions.first { it.title?.toString() == "\u2192" }
        assertThat(forwardAction.isEnabled).isFalse()
    }

    @Test
    fun displayHistory_isAccessible() {
        assertThat(screen.displayHistory).isNotNull()
    }

    @Test
    fun afterTwoDisplays_backButtonEnabled() {
        screen.displayHistory.addEntry("key1")
        screen.displayHistory.addEntry("key2")
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        val backAction = actions.first { it.title?.toString() == "\u2190" }
        assertThat(backAction.isEnabled).isTrue()
    }

    @Test
    fun afterGoBack_forwardButtonEnabled() {
        screen.displayHistory.addEntry("key1")
        screen.displayHistory.addEntry("key2")
        screen.displayHistory.goBack()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        val forwardAction = actions.first { it.title?.toString() == "\u2192" }
        assertThat(forwardAction.isEnabled).isTrue()
    }
}
