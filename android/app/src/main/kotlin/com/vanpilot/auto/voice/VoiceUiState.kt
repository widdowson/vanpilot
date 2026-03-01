package com.vanpilot.auto.voice

/**
 * Data class representing the current voice state for UI consumption.
 * Observable via [VoiceStateMachine.uiState] StateFlow.
 */
data class VoiceUiState(
    val currentState: VoiceState = VoiceState.IDLE,
    val partialTranscript: String = "",
    val lastError: String? = null,
    val isListening: Boolean = false,
    val isSpeaking: Boolean = false
)
