package com.vanpilot.auto.voice

/**
 * Listener for speech recognition events.
 */
interface SpeechToTextListener {
    /** Final recognition result. */
    fun onResult(text: String)
    /** Partial (interim) recognition result. */
    fun onPartialResult(text: String)
    /** Recognition error. [errorCode] mirrors SpeechRecognizer error codes. */
    fun onError(errorCode: Int, message: String)
    /** The recognizer is ready to accept speech. */
    fun onReadyForSpeech()
    /** The user has stopped speaking. */
    fun onEndOfSpeech()
}

/**
 * Factory interface that abstracts Android SpeechRecognizer.
 * Production code creates an AndroidSpeechRecognizerFactory;
 * tests supply a fake.
 */
interface SpeechRecognizerFactory {
    fun startRecognition(listener: SpeechToTextListener)
    fun stopRecognition()
    fun destroy()
    fun isAvailable(): Boolean
}

/**
 * Manages speech-to-text recognition.
 *
 * Wraps a [SpeechRecognizerFactory] to decouple from the Android
 * SpeechRecognizer framework class, enabling pure-JVM testing.
 *
 * Usage:
 * ```
 * val stt = SpeechToTextManager(factory)
 * stt.listener = myListener
 * stt.startListening()
 * ```
 */
class SpeechToTextManager(private val recognizerFactory: SpeechRecognizerFactory) {

    companion object {
        const val TAG = "VanPilotSTT"
    }

    /** External listener for recognition events. */
    var listener: SpeechToTextListener? = null

    /** Whether the recognizer is currently listening. */
    var isListening: Boolean = false
        private set

    /**
     * Start listening for speech.
     * @return true if listening started, false if already listening.
     */
    fun startListening(): Boolean {
        if (isListening) return false
        isListening = true
        recognizerFactory.startRecognition(internalListener)
        return true
    }

    /**
     * Stop listening. No-op if not currently listening.
     */
    fun stopListening() {
        if (!isListening) return
        isListening = false
        recognizerFactory.stopRecognition()
    }

    /**
     * Release all resources. Must be called when no longer needed.
     */
    fun destroy() {
        stopListening()
        recognizerFactory.destroy()
    }

    /**
     * Internal listener that updates [isListening] state before
     * forwarding events to the external [listener].
     */
    private val internalListener = object : SpeechToTextListener {
        override fun onResult(text: String) {
            isListening = false
            listener?.onResult(text)
        }

        override fun onPartialResult(text: String) {
            listener?.onPartialResult(text)
        }

        override fun onError(errorCode: Int, message: String) {
            isListening = false
            listener?.onError(errorCode, message)
        }

        override fun onReadyForSpeech() {
            listener?.onReadyForSpeech()
        }

        override fun onEndOfSpeech() {
            listener?.onEndOfSpeech()
        }
    }
}
