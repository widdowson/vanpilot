package com.vanpilot.auto.connectivity

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class ConnectionMonitorTest {

    private lateinit var monitor: ConnectionMonitor
    private val stateChanges = mutableListOf<ConnectionState>()

    @Before
    fun setUp() {
        monitor = ConnectionMonitor()
        monitor.addListener { state -> stateChanges.add(state) }
    }

    @Test
    fun initialState_isDisconnected() {
        assertThat(monitor.state).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun onSuccessfulRpc_transitionsToConnected() {
        monitor.onRpcSuccess()
        assertThat(monitor.state).isEqualTo(ConnectionState.CONNECTED)
    }

    @Test
    fun onRpcFailure_transitionsToDisconnected() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        assertThat(monitor.state).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun onReconnectAttempt_transitionsToReconnecting() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        assertThat(monitor.state).isEqualTo(ConnectionState.RECONNECTING)
    }

    @Test
    fun onSuccessAfterReconnecting_transitionsToConnected() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        monitor.onRpcSuccess()
        assertThat(monitor.state).isEqualTo(ConnectionState.CONNECTED)
    }

    @Test
    fun listener_notifiedOnStateChange() {
        monitor.onRpcSuccess()
        assertThat(stateChanges).containsExactly(ConnectionState.CONNECTED)
    }

    @Test
    fun listener_notNotifiedWhenStateSame() {
        monitor.onRpcSuccess()
        monitor.onRpcSuccess()
        assertThat(stateChanges).containsExactly(ConnectionState.CONNECTED)
    }

    @Test
    fun listener_notifiedOnDisconnect() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        assertThat(stateChanges).containsExactly(
            ConnectionState.CONNECTED,
            ConnectionState.DISCONNECTED
        ).inOrder()
    }

    @Test
    fun listener_notifiedOnReconnecting() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        assertThat(stateChanges).containsExactly(
            ConnectionState.CONNECTED,
            ConnectionState.DISCONNECTED,
            ConnectionState.RECONNECTING
        ).inOrder()
    }

    @Test
    fun multipleListeners_allNotified() {
        val secondListenerChanges = mutableListOf<ConnectionState>()
        monitor.addListener { state -> secondListenerChanges.add(state) }
        monitor.onRpcSuccess()
        assertThat(stateChanges).containsExactly(ConnectionState.CONNECTED)
        assertThat(secondListenerChanges).containsExactly(ConnectionState.CONNECTED)
    }

    @Test
    fun removeListener_noLongerNotified() {
        val listener: (ConnectionState) -> Unit = { state -> stateChanges.add(state) }
        val monitor2 = ConnectionMonitor()
        monitor2.addListener(listener)
        monitor2.removeListener(listener)
        monitor2.onRpcSuccess()
        assertThat(stateChanges).isEmpty()
    }

    @Test
    fun consecutiveFailures_onlyOneDisconnectNotification() {
        monitor.onRpcSuccess()
        stateChanges.clear()
        monitor.onRpcFailure()
        monitor.onRpcFailure()
        monitor.onRpcFailure()
        assertThat(stateChanges).containsExactly(ConnectionState.DISCONNECTED)
    }

    @Test
    fun consecutiveFailureCount_tracksFailures() {
        assertThat(monitor.consecutiveFailures).isEqualTo(0)
        monitor.onRpcFailure()
        assertThat(monitor.consecutiveFailures).isEqualTo(1)
        monitor.onRpcFailure()
        assertThat(monitor.consecutiveFailures).isEqualTo(2)
        monitor.onRpcSuccess()
        assertThat(monitor.consecutiveFailures).isEqualTo(0)
    }

    @Test
    fun wasRecentlyReconnected_trueAfterReconnection() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        monitor.onRpcSuccess()
        assertThat(monitor.wasRecentlyReconnected).isTrue()
    }

    @Test
    fun wasRecentlyReconnected_falseWhenStablyConnected() {
        monitor.onRpcSuccess()
        assertThat(monitor.wasRecentlyReconnected).isFalse()
    }

    @Test
    fun clearRecentReconnection_resetsFlag() {
        monitor.onRpcSuccess()
        monitor.onRpcFailure()
        monitor.onReconnectAttempt()
        monitor.onRpcSuccess()
        monitor.clearRecentReconnection()
        assertThat(monitor.wasRecentlyReconnected).isFalse()
    }
}
