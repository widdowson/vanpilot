package com.vanpilot.auto.connectivity

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class ConnectionStateTest {

    @Test
    fun initialState_isDisconnected() {
        assertThat(ConnectionState.DISCONNECTED.isOnline).isFalse()
    }

    @Test
    fun connectedState_isOnline() {
        assertThat(ConnectionState.CONNECTED.isOnline).isTrue()
    }

    @Test
    fun disconnectedState_isNotOnline() {
        assertThat(ConnectionState.DISCONNECTED.isOnline).isFalse()
    }

    @Test
    fun reconnectingState_isNotOnline() {
        assertThat(ConnectionState.RECONNECTING.isOnline).isFalse()
    }

    @Test
    fun connectedState_allowsVoiceInput() {
        assertThat(ConnectionState.CONNECTED.voiceInputEnabled).isTrue()
    }

    @Test
    fun disconnectedState_disablesVoiceInput() {
        assertThat(ConnectionState.DISCONNECTED.voiceInputEnabled).isFalse()
    }

    @Test
    fun reconnectingState_disablesVoiceInput() {
        assertThat(ConnectionState.RECONNECTING.voiceInputEnabled).isFalse()
    }

    @Test
    fun connectedState_showsNoDisconnectIndicator() {
        assertThat(ConnectionState.CONNECTED.showDisconnectIndicator).isFalse()
    }

    @Test
    fun disconnectedState_showsDisconnectIndicator() {
        assertThat(ConnectionState.DISCONNECTED.showDisconnectIndicator).isTrue()
    }

    @Test
    fun reconnectingState_showsDisconnectIndicator() {
        assertThat(ConnectionState.RECONNECTING.showDisconnectIndicator).isTrue()
    }
}
