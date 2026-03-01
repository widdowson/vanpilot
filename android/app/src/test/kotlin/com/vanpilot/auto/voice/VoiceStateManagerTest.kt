package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VoiceStateManager.
 * Tests pure Kotlin state machine logic without requiring the Android runtime.
 */
@RunWith(JUnit4::class)
class VoiceStateManagerTest {

    private lateinit var manager: VoiceStateManager
    private val stateChanges = mutableListOf<VoiceState>()

    @Before
    fun setUp() {
        manager = VoiceStateManager()
        stateChanges.clear()
        manager.onStateChanged = { stateChanges.add(it) }
    }

    // --- Initial state ---

    @Test
    fun initialState_isIdle() {
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun initialState_isOnline() {
        assertThat(manager.isOnline).isTrue()
    }

    @Test
    fun initialState_noError() {
        assertThat(manager.lastError).isNull()
    }

    // --- Online/offline transitions ---

    @Test
    fun setOffline_transitionsToDisabled() {
        manager.setOnline(false)
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
        assertThat(manager.isOnline).isFalse()
    }

    @Test
    fun setOnline_fromDisabled_transitionsToIdle() {
        manager.setOnline(false)
        manager.setOnline(true)
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
        assertThat(manager.isOnline).isTrue()
    }

    @Test
    fun setOffline_whileListening_transitionsToDisabled() {
        manager.startListening()
        manager.setOnline(false)
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
    }

    @Test
    fun setOffline_whileSpeaking_transitionsToDisabled() {
        manager.startSpeaking()
        manager.setOnline(false)
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
    }

    // --- Listening transitions ---

    @Test
    fun startListening_fromIdle_transitionsToListening() {
        val result = manager.startListening()
        assertThat(result).isTrue()
        assertThat(manager.state).isEqualTo(VoiceState.LISTENING)
    }

    @Test
    fun startListening_fromDisabled_returnsFalse() {
        manager.setOnline(false)
        val result = manager.startListening()
        assertThat(result).isFalse()
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
    }

    @Test
    fun startListening_fromSpeaking_returnsFalse() {
        manager.startSpeaking()
        val result = manager.startListening()
        assertThat(result).isFalse()
        assertThat(manager.state).isEqualTo(VoiceState.SPEAKING)
    }

    @Test
    fun startListening_fromListening_returnsFalse() {
        manager.startListening()
        val result = manager.startListening()
        assertThat(result).isFalse()
        assertThat(manager.state).isEqualTo(VoiceState.LISTENING)
    }

    // --- Recognition result transitions ---

    @Test
    fun onRecognitionResult_fromListening_transitionsToProcessing() {
        manager.startListening()
        manager.onRecognitionResult("hello world")
        assertThat(manager.state).isEqualTo(VoiceState.PROCESSING)
    }

    @Test
    fun onRecognitionResult_fromIdle_noTransition() {
        manager.onRecognitionResult("hello world")
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    // --- Recognition error ---

    @Test
    fun onRecognitionError_transitionsToError() {
        manager.startListening()
        manager.onRecognitionError("No speech detected")
        assertThat(manager.state).isEqualTo(VoiceState.ERROR)
        assertThat(manager.lastError).isEqualTo("No speech detected")
    }

    // --- Speaking transitions ---

    @Test
    fun startSpeaking_fromIdle_transitionsToSpeaking() {
        val result = manager.startSpeaking()
        assertThat(result).isTrue()
        assertThat(manager.state).isEqualTo(VoiceState.SPEAKING)
    }

    @Test
    fun startSpeaking_fromDisabled_returnsFalse() {
        manager.setOnline(false)
        val result = manager.startSpeaking()
        assertThat(result).isFalse()
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
    }

    @Test
    fun onSpeakingComplete_fromSpeaking_transitionsToIdle() {
        manager.startSpeaking()
        manager.onSpeakingComplete()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun onSpeakingComplete_fromIdle_noTransition() {
        manager.onSpeakingComplete()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    // --- Processing transitions ---

    @Test
    fun onProcessingComplete_fromProcessing_transitionsToIdle() {
        manager.startListening()
        manager.onRecognitionResult("test")
        manager.onProcessingComplete()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun onProcessingComplete_fromIdle_noTransition() {
        manager.onProcessingComplete()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    // --- Reset ---

    @Test
    fun reset_fromError_transitionsToIdle() {
        manager.startListening()
        manager.onRecognitionError("error")
        manager.reset()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
        assertThat(manager.lastError).isNull()
    }

    @Test
    fun reset_whileOffline_transitionsToDisabled() {
        manager.setOnline(false)
        manager.reset()
        assertThat(manager.state).isEqualTo(VoiceState.DISABLED)
    }

    // --- Listener notifications ---

    @Test
    fun stateChanges_areNotified() {
        manager.startListening()
        manager.onRecognitionResult("test")
        manager.onProcessingComplete()

        assertThat(stateChanges).containsExactly(
            VoiceState.LISTENING,
            VoiceState.PROCESSING,
            VoiceState.IDLE
        ).inOrder()
    }

    @Test
    fun noNotification_whenStateUnchanged() {
        manager.onSpeakingComplete() // already IDLE, should not notify
        assertThat(stateChanges).isEmpty()
    }

    // --- Cancel listening ---

    @Test
    fun cancelListening_fromListening_transitionsToIdle() {
        manager.startListening()
        manager.cancelListening()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun cancelListening_fromIdle_noTransition() {
        manager.cancelListening()
        assertThat(manager.state).isEqualTo(VoiceState.IDLE)
        assertThat(stateChanges).isEmpty()
    }
}
