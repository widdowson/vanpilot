package com.vanpilot.auto

import androidx.car.app.model.CarColor
import androidx.car.app.model.CarIcon
import androidx.car.app.navigation.model.NavigationTemplate
import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.connectivity.ConnectionMonitor
import com.vanpilot.auto.connectivity.ConnectionState
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenConnectionTest {

    private lateinit var monitor: ConnectionMonitor
    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        monitor = ConnectionMonitor()
        screen = VanPilotScreen(carContext, monitor)
    }

    @Test
    fun defaultState_isDisconnected() {
        assertThat(monitor.state).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun visualTab_disconnected_actionStripHasRedIndicator() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        // Should have PAN + connection indicator
        assertThat(actions).hasSize(2)
        val indicatorAction = actions[0]
        assertThat(indicatorAction.icon!!.tint).isEqualTo(CarColor.RED)
    }

    @Test
    fun visualTab_connected_actionStripHasGreenIndicator() {
        monitor.onRpcSuccess()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        assertThat(actions).hasSize(2)
        val indicatorAction = actions[0]
        assertThat(indicatorAction.icon!!.tint).isEqualTo(CarColor.GREEN)
    }

    @Test
    fun visualTab_reconnecting_actionStripHasYellowIndicator() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actions = navTemplate.actionStrip!!.actions
        assertThat(actions).hasSize(2)
        val indicatorAction = actions[0]
        assertThat(indicatorAction.icon!!.tint).isEqualTo(CarColor.YELLOW)
    }

    @Test
    fun connectionStateChange_triggersInvalidate() {
        // Get initial template to confirm it works
        screen.onGetTemplate()
        // Transition to connected — listener should call invalidate()
        monitor.onRpcSuccess()
        // If invalidate was called, onGetTemplate should reflect new state
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val indicatorAction = navTemplate.actionStrip!!.actions[0]
        assertThat(indicatorAction.icon!!.tint).isEqualTo(CarColor.GREEN)
    }

    @Test
    fun defaultConstructor_createsOwnConnectionMonitor() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        val defaultScreen = VanPilotScreen(carContext)
        assertThat(defaultScreen.connectionMonitor).isNotNull()
        assertThat(defaultScreen.connectionMonitor.state).isEqualTo(ConnectionState.DISCONNECTED)
    }
}
