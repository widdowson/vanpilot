package com.vanpilot.auto.voice

/**
 * The possible states of the voice I/O system.
 */
enum class VoiceState {
    /** Default state, waiting for user to activate voice. */
    IDLE,

    /** SpeechRecognizer is actively capturing audio. */
    LISTENING,

    /** STT result received, sending to supervisor via gRPC. */
    PROCESSING,

    /** TTS is reading a response aloud. */
    SPEAKING,

    /** Voice not available (e.g., network disconnected). */
    DISABLED
}
