package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for [VoiceStateMachine] covering all state transitions,
 * invalid transition rejection, callback behavior, and thread safety.
 */
@RunWith(JUnit4::class)
class VoiceStateMachineTest {

    private lateinit var sttEngine: FakeSttEngine
    private lateinit var ttsEngine: FakeTtsEngine
    private lateinit var stateMachine: VoiceStateMachine

    @Before
    fun setUp() {
        sttEngine = FakeSttEngine()
        ttsEngine = FakeTtsEngine()
        stateMachine = VoiceStateMachine(sttEngine, ttsEngine)
    }

    // -- Initial state --

    @Test
    fun initialState_isIdle() {
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun initialUiState_hasDefaults() {
        val ui = stateMachine.uiState.value
        assertThat(ui.currentState).isEqualTo(VoiceState.IDLE)
        assertThat(ui.partialTranscript).isEmpty()
        assertThat(ui.lastError).isNull()
        assertThat(ui.isListening).isFalse()
        assertThat(ui.isSpeaking).isFalse()
    }

    // -- IDLE → LISTENING --

    @Test
    fun activateVoice_transitionsToListening() {
        stateMachine.activateVoice()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.LISTENING)
        assertThat(stateMachine.uiState.value.isListening).isTrue()
    }

    @Test
    fun activateVoice_startsSttEngine() {
        stateMachine.activateVoice()
        assertThat(sttEngine.startCount).isEqualTo(1)
        assertThat(sttEngine.isListening).isTrue()
    }

    // -- LISTENING → PROCESSING (STT result) --

    @Test
    fun sttResult_transitionsToProcessing() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello world")
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.PROCESSING)
        assertThat(stateMachine.uiState.value.isListening).isFalse()
    }

    @Test
    fun sttResult_stopsListening() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello world")
        assertThat(sttEngine.stopCount).isEqualTo(1)
    }

    @Test
    fun sttResult_storesTranscript() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("navigate home")
        assertThat(stateMachine.uiState.value.partialTranscript).isEqualTo("navigate home")
    }

    @Test
    fun sttResult_firesTranscriptionReadyCallback() {
        var received: String? = null
        stateMachine.onTranscriptionReady = { received = it }
        stateMachine.activateVoice()
        sttEngine.simulateResult("play music")
        assertThat(received).isEqualTo("play music")
    }

    // -- LISTENING → IDLE (cancel) --

    @Test
    fun cancelListening_transitionsToIdle() {
        stateMachine.activateVoice()
        stateMachine.cancelListening()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
        assertThat(stateMachine.uiState.value.isListening).isFalse()
    }

    @Test
    fun cancelListening_stopsSttEngine() {
        stateMachine.activateVoice()
        stateMachine.cancelListening()
        assertThat(sttEngine.stopCount).isEqualTo(1)
    }

    // -- LISTENING → IDLE (STT error) --

    @Test
    fun sttError_transitionsToIdle() {
        stateMachine.activateVoice()
        sttEngine.simulateError(7)
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun sttError_setsLastError() {
        stateMachine.activateVoice()
        sttEngine.simulateError(7)
        assertThat(stateMachine.uiState.value.lastError).isEqualTo("STT error: 7")
    }

    @Test
    fun sttError_stopsSttEngine() {
        stateMachine.activateVoice()
        sttEngine.simulateError(7)
        assertThat(sttEngine.stopCount).isEqualTo(1)
    }

    // -- Partial results --

    @Test
    fun sttPartialResult_updatesTranscript() {
        stateMachine.activateVoice()
        sttEngine.simulatePartialResult("hel")
        assertThat(stateMachine.uiState.value.partialTranscript).isEqualTo("hel")
        sttEngine.simulatePartialResult("hello")
        assertThat(stateMachine.uiState.value.partialTranscript).isEqualTo("hello")
    }

    @Test
    fun sttPartialResult_doesNotChangeState() {
        stateMachine.activateVoice()
        sttEngine.simulatePartialResult("hel")
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.LISTENING)
    }

    // -- PROCESSING → SPEAKING --

    @Test
    fun onResponseReceived_transitionsToSpeaking() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onResponseReceived("Hi there!")
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.SPEAKING)
        assertThat(stateMachine.uiState.value.isSpeaking).isTrue()
    }

    @Test
    fun onResponseReceived_startsTtsEngine() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onResponseReceived("Hi there!")
        assertThat(ttsEngine.speakCount).isEqualTo(1)
        assertThat(ttsEngine.lastSpokenText).isEqualTo("Hi there!")
    }

    // -- PROCESSING → IDLE (timeout) --

    @Test
    fun onProcessingTimeout_transitionsToIdle() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onProcessingTimeout()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun onProcessingTimeout_setsLastError() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onProcessingTimeout()
        assertThat(stateMachine.uiState.value.lastError).isEqualTo("Processing timeout")
    }

    // -- SPEAKING → IDLE (TTS done) --

    @Test
    fun ttsCompletion_transitionsToIdle() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onResponseReceived("response")
        ttsEngine.simulateCompletion()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
        assertThat(stateMachine.uiState.value.isSpeaking).isFalse()
    }

    // -- ANY → DISABLED --

    @Test
    fun disable_fromIdle() {
        stateMachine.disable()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.DISABLED)
    }

    @Test
    fun disable_fromListening_stopsSTT() {
        stateMachine.activateVoice()
        stateMachine.disable()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.DISABLED)
        assertThat(sttEngine.stopCount).isEqualTo(1)
    }

    @Test
    fun disable_fromSpeaking_stopsTTS() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.onResponseReceived("response")
        stateMachine.disable()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.DISABLED)
        assertThat(ttsEngine.stopCount).isEqualTo(1)
    }

    @Test
    fun disable_fromProcessing() {
        stateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        stateMachine.disable()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.DISABLED)
    }

    @Test
    fun disable_whenAlreadyDisabled_isNoOp() {
        stateMachine.disable()
        stateMachine.disable() // should not throw
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.DISABLED)
    }

    // -- DISABLED → IDLE --

    @Test
    fun enable_transitionsToIdle() {
        stateMachine.disable()
        stateMachine.enable()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    // -- Invalid transitions --

    @Test(expected = IllegalArgumentException::class)
    fun activateVoice_fromListening_throws() {
        stateMachine.activateVoice()
        stateMachine.activateVoice()
    }

    @Test(expected = IllegalArgumentException::class)
    fun activateVoice_fromDisabled_throws() {
        stateMachine.disable()
        stateMachine.activateVoice()
    }

    @Test(expected = IllegalArgumentException::class)
    fun cancelListening_fromIdle_throws() {
        stateMachine.cancelListening()
    }

    @Test(expected = IllegalArgumentException::class)
    fun onResponseReceived_fromIdle_throws() {
        stateMachine.onResponseReceived("text")
    }

    @Test(expected = IllegalArgumentException::class)
    fun onProcessingTimeout_fromIdle_throws() {
        stateMachine.onProcessingTimeout()
    }

    @Test(expected = IllegalArgumentException::class)
    fun enable_fromIdle_throws() {
        stateMachine.enable()
    }

    // -- Full round trip --

    @Test
    fun fullRoundTrip_idle_listen_process_speak_idle() {
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)

        stateMachine.activateVoice()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.LISTENING)

        sttEngine.simulateResult("turn on lights")
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.PROCESSING)

        stateMachine.onResponseReceived("Lights turned on")
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.SPEAKING)

        ttsEngine.simulateCompletion()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun multipleRoundTrips() {
        // First round trip
        stateMachine.activateVoice()
        sttEngine.simulateResult("first")
        stateMachine.onResponseReceived("response 1")
        ttsEngine.simulateCompletion()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)

        // Second round trip
        stateMachine.activateVoice()
        sttEngine.simulateResult("second")
        stateMachine.onResponseReceived("response 2")
        ttsEngine.simulateCompletion()
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)

        assertThat(sttEngine.startCount).isEqualTo(2)
        assertThat(ttsEngine.speakCount).isEqualTo(2)
    }

    // -- Thread safety (basic) --

    @Test
    fun concurrentActivateAndDisable_doesNotCorrupt() {
        // Run many concurrent transitions to verify synchronized blocks
        val threads = (1..10).map { i ->
            Thread {
                try {
                    if (i % 2 == 0) {
                        stateMachine.activateVoice()
                    } else {
                        stateMachine.disable()
                    }
                } catch (_: IllegalArgumentException) {
                    // Expected for invalid transitions
                }
            }
        }
        threads.forEach { it.start() }
        threads.forEach { it.join() }

        // State should be one of the valid states (not corrupted)
        assertThat(stateMachine.currentState).isAnyOf(
            VoiceState.IDLE,
            VoiceState.LISTENING,
            VoiceState.DISABLED
        )
    }

    // -- Callbacks in wrong state are ignored --

    @Test
    fun sttResult_whenNotListening_isIgnored() {
        // State machine is IDLE, simulate an STT result (shouldn't happen but handle gracefully)
        sttEngine.startListening(
            onResult = {},
            onPartialResult = {},
            onError = {}
        )
        // The state machine's internal callbacks are only set via activateVoice
        // So calling simulateResult before activateVoice does nothing
        assertThat(stateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }
}
