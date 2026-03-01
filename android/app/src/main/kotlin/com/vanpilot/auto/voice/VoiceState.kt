package com.vanpilot.auto.voice

/**
 * Represents the current state of the voice I/O system.
 */
enum class VoiceState {
    /** Ready for voice input, not actively processing. */
    IDLE,
    /** STT is actively listening for speech. */
    LISTENING,
    /** Speech recognized; sending transcribed text to the backend. */
    PROCESSING,
    /** TTS is reading an agent response aloud. */
    SPEAKING,
    /** Offline — voice input/output is disabled. */
    DISABLED,
    /** An error occurred (recoverable via reset). */
    ERROR
}

/**
 * Manages voice state transitions and enforces valid state changes.
 * Pure Kotlin — no Android framework dependencies.
 */
class VoiceStateManager {

    /** Current voice state. */
    var state: VoiceState = VoiceState.IDLE
        private set

    /** Whether the device has network connectivity to the backend. */
    var isOnline: Boolean = true
        private set

    /** Description of the last error, or null if no error. */
    var lastError: String? = null
        private set

    /** Called whenever [state] changes. */
    var onStateChanged: ((VoiceState) -> Unit)? = null

    /**
     * Updates connectivity status. Going offline disables voice;
     * coming back online restores IDLE if currently DISABLED.
     */
    fun setOnline(online: Boolean) {
        isOnline = online
        if (!online) {
            transitionTo(VoiceState.DISABLED)
        } else if (state == VoiceState.DISABLED) {
            transitionTo(VoiceState.IDLE)
        }
    }

    /**
     * Attempt to start listening. Only valid from IDLE.
     * @return true if the transition succeeded.
     */
    fun startListening(): Boolean {
        if (state != VoiceState.IDLE) return false
        return transitionTo(VoiceState.LISTENING)
    }

    /**
     * Cancel an in-progress listening session. Returns to IDLE.
     */
    fun cancelListening() {
        if (state == VoiceState.LISTENING) {
            transitionTo(VoiceState.IDLE)
        }
    }

    /**
     * Called when STT produces a final recognition result.
     * Transitions from LISTENING to PROCESSING.
     */
    fun onRecognitionResult(text: String) {
        if (state == VoiceState.LISTENING) {
            transitionTo(VoiceState.PROCESSING)
        }
    }

    /**
     * Called when STT encounters an error.
     * Stores the error message and transitions to ERROR.
     */
    fun onRecognitionError(error: String) {
        lastError = error
        transitionTo(VoiceState.ERROR)
    }

    /**
     * Attempt to start TTS playback. Not allowed when DISABLED.
     * Allowed from any non-DISABLED state, including LISTENING —
     * the higher-level controller is responsible for stopping STT
     * before calling this if mutual exclusion is desired.
     * @return true if the transition succeeded.
     */
    fun startSpeaking(): Boolean {
        if (state == VoiceState.DISABLED) return false
        return transitionTo(VoiceState.SPEAKING)
    }

    /**
     * Called when TTS finishes reading. Returns to IDLE.
     */
    fun onSpeakingComplete() {
        if (state == VoiceState.SPEAKING) {
            transitionTo(VoiceState.IDLE)
        }
    }

    /**
     * Called when the backend acknowledges the transcribed input.
     * Transitions from PROCESSING to IDLE.
     */
    fun onProcessingComplete() {
        if (state == VoiceState.PROCESSING) {
            transitionTo(VoiceState.IDLE)
        }
    }

    /**
     * Reset to a clean state. Clears errors.
     * Goes to IDLE if online, DISABLED if offline.
     */
    fun reset() {
        lastError = null
        transitionTo(if (isOnline) VoiceState.IDLE else VoiceState.DISABLED)
    }

    private fun transitionTo(newState: VoiceState): Boolean {
        if (state == newState) return false
        state = newState
        onStateChanged?.invoke(newState)
        return true
    }
}
