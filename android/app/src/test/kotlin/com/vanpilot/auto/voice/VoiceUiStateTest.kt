package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for [VoiceUiState] data class.
 */
@RunWith(JUnit4::class)
class VoiceUiStateTest {

    @Test
    fun defaultValues() {
        val state = VoiceUiState()
        assertThat(state.currentState).isEqualTo(VoiceState.IDLE)
        assertThat(state.partialTranscript).isEmpty()
        assertThat(state.lastError).isNull()
        assertThat(state.isListening).isFalse()
        assertThat(state.isSpeaking).isFalse()
    }

    @Test
    fun listeningState() {
        val state = VoiceUiState(
            currentState = VoiceState.LISTENING,
            isListening = true
        )
        assertThat(state.currentState).isEqualTo(VoiceState.LISTENING)
        assertThat(state.isListening).isTrue()
        assertThat(state.isSpeaking).isFalse()
    }

    @Test
    fun speakingState() {
        val state = VoiceUiState(
            currentState = VoiceState.SPEAKING,
            isSpeaking = true
        )
        assertThat(state.isSpeaking).isTrue()
        assertThat(state.isListening).isFalse()
    }

    @Test
    fun withPartialTranscript() {
        val state = VoiceUiState(
            currentState = VoiceState.LISTENING,
            partialTranscript = "hello wor",
            isListening = true
        )
        assertThat(state.partialTranscript).isEqualTo("hello wor")
    }

    @Test
    fun withError() {
        val state = VoiceUiState(lastError = "STT error: 7")
        assertThat(state.lastError).isEqualTo("STT error: 7")
    }

    @Test
    fun copy_preservesOtherFields() {
        val original = VoiceUiState(
            currentState = VoiceState.LISTENING,
            partialTranscript = "hello",
            isListening = true
        )
        val updated = original.copy(partialTranscript = "hello world")
        assertThat(updated.currentState).isEqualTo(VoiceState.LISTENING)
        assertThat(updated.partialTranscript).isEqualTo("hello world")
        assertThat(updated.isListening).isTrue()
    }

    @Test
    fun equality() {
        val a = VoiceUiState()
        val b = VoiceUiState()
        assertThat(a).isEqualTo(b)
        assertThat(a.hashCode()).isEqualTo(b.hashCode())
    }

    @Test
    fun inequality_differentState() {
        val a = VoiceUiState(currentState = VoiceState.IDLE)
        val b = VoiceUiState(currentState = VoiceState.DISABLED)
        assertThat(a).isNotEqualTo(b)
    }
}
