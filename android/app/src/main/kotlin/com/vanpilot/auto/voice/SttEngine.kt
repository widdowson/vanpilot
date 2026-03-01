package com.vanpilot.auto.voice

import java.util.Locale

/**
 * Abstraction over speech-to-text functionality.
 * Implementations wrap platform APIs (e.g., Android SpeechRecognizer).
 * Test code uses fake implementations.
 */
interface SttEngine {

    /** Whether the engine is currently listening for speech. */
    val isListening: Boolean

    /**
     * Start listening for speech input.
     *
     * @param locale Language locale for recognition.
     * @param enablePartialResults Whether to deliver partial results.
     * @param onResult Called with the final transcribed text.
     * @param onPartialResult Called with partial transcription updates.
     * @param onError Called with an error code on failure.
     */
    fun startListening(
        locale: Locale = Locale.US,
        enablePartialResults: Boolean = true,
        onResult: (String) -> Unit,
        onPartialResult: (String) -> Unit,
        onError: (Int) -> Unit
    )

    /** Stop listening. */
    fun stopListening()

    /** Release all resources. */
    fun destroy()
}
