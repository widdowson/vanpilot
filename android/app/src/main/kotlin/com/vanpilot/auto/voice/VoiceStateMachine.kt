package com.vanpilot.auto.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Thread-safe state machine coordinating STT and TTS.
 *
 * States: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
 * Any state can transition to DISABLED; DISABLED transitions back to IDLE.
 *
 * The state machine ensures STT and TTS never run simultaneously.
 */
class VoiceStateMachine(
    private val sttEngine: SttEngine,
    private val ttsEngine: TtsEngine
) {
    private val _uiState = MutableStateFlow(VoiceUiState())

    /** Observable UI state. */
    val uiState: StateFlow<VoiceUiState> = _uiState.asStateFlow()

    /** Shortcut to the current voice state. */
    val currentState: VoiceState get() = _uiState.value.currentState

    private val lock = Any()

    /**
     * Called when STT produces a final transcript and the text has been
     * sent to the supervisor. External code should observe this to
     * trigger the gRPC SendUserInput call.
     */
    var onTranscriptionReady: ((String) -> Unit)? = null

    /** Transition IDLE → LISTENING. Starts the STT engine. */
    fun activateVoice() {
        synchronized(lock) {
            require(currentState == VoiceState.IDLE) {
                "Cannot activate voice from $currentState"
            }
            sttEngine.startListening(
                onResult = { text -> onSttResult(text) },
                onPartialResult = { text -> onSttPartialResult(text) },
                onError = { code -> onSttError(code) }
            )
            updateState(VoiceState.LISTENING)
        }
    }

    /** Transition LISTENING → IDLE. Cancels STT. */
    fun cancelListening() {
        synchronized(lock) {
            require(currentState == VoiceState.LISTENING) {
                "Cannot cancel listening from $currentState"
            }
            sttEngine.stopListening()
            updateState(VoiceState.IDLE)
        }
    }

    /** Transition PROCESSING → SPEAKING. Starts TTS with the response. */
    fun onResponseReceived(text: String) {
        synchronized(lock) {
            require(currentState == VoiceState.PROCESSING) {
                "Cannot receive response from $currentState"
            }
            ttsEngine.setOnUtteranceCompleted { onTtsCompleted() }
            ttsEngine.speak(text)
            updateState(VoiceState.SPEAKING)
        }
    }

    /** Transition PROCESSING → IDLE on timeout or error. */
    fun onProcessingTimeout() {
        synchronized(lock) {
            require(currentState == VoiceState.PROCESSING) {
                "Cannot timeout from $currentState"
            }
            updateState(VoiceState.IDLE, lastError = "Processing timeout")
        }
    }

    /** Transition ANY → DISABLED. Stops active STT/TTS. */
    fun disable() {
        synchronized(lock) {
            if (currentState == VoiceState.DISABLED) return
            when (currentState) {
                VoiceState.LISTENING -> sttEngine.stopListening()
                VoiceState.SPEAKING -> ttsEngine.stop()
                else -> {}
            }
            updateState(VoiceState.DISABLED)
        }
    }

    /** Transition DISABLED → IDLE. */
    fun enable() {
        synchronized(lock) {
            require(currentState == VoiceState.DISABLED) {
                "Cannot enable from $currentState"
            }
            updateState(VoiceState.IDLE)
        }
    }

    // -- Internal callbacks from engines --

    private fun onSttResult(text: String) {
        synchronized(lock) {
            if (currentState != VoiceState.LISTENING) return
            sttEngine.stopListening()
            updateState(VoiceState.PROCESSING, partialTranscript = text)
            onTranscriptionReady?.invoke(text)
        }
    }

    private fun onSttPartialResult(text: String) {
        synchronized(lock) {
            if (currentState != VoiceState.LISTENING) return
            _uiState.value = _uiState.value.copy(partialTranscript = text)
        }
    }

    private fun onSttError(code: Int) {
        synchronized(lock) {
            if (currentState != VoiceState.LISTENING) return
            sttEngine.stopListening()
            updateState(VoiceState.IDLE, lastError = "STT error: $code")
        }
    }

    private fun onTtsCompleted() {
        synchronized(lock) {
            if (currentState != VoiceState.SPEAKING) return
            updateState(VoiceState.IDLE)
        }
    }

    private fun updateState(
        newState: VoiceState,
        partialTranscript: String = "",
        lastError: String? = null
    ) {
        _uiState.value = VoiceUiState(
            currentState = newState,
            partialTranscript = partialTranscript,
            lastError = lastError,
            isListening = newState == VoiceState.LISTENING,
            isSpeaking = newState == VoiceState.SPEAKING
        )
    }
}
