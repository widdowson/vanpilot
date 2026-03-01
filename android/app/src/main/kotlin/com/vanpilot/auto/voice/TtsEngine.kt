package com.vanpilot.auto.voice

/**
 * Abstraction over text-to-speech functionality.
 * Implementations wrap platform APIs (e.g., Android TextToSpeech).
 * Test code uses fake implementations.
 */
interface TtsEngine {

    /** Whether the engine is currently speaking. */
    val isSpeaking: Boolean

    /** Speak the given text, replacing any queued speech. */
    fun speak(text: String)

    /** Stop any current speech. */
    fun stop()

    /** Release all resources. */
    fun shutdown()

    /** Set a callback invoked when the current utterance finishes. */
    fun setOnUtteranceCompleted(callback: (() -> Unit)?)
}
