package com.vanpilot.auto.voice

/**
 * Data class representing the current voice state for UI consumption.
 * Observable via [VoiceStateMachine.uiState] StateFlow.
 *
 * [isListening] and [isSpeaking] are derived from [currentState] to
 * prevent semantically invalid states (e.g., IDLE + isListening=true).
 */
data class VoiceUiState(
    val currentState: VoiceState = VoiceState.IDLE,
    val partialTranscript: String = "",
    val lastError: String? = null
) {
    val isListening: Boolean get() = currentState == VoiceState.LISTENING
    val isSpeaking: Boolean get() = currentState == VoiceState.SPEAKING
}
