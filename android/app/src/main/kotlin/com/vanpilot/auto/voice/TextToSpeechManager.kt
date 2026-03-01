package com.vanpilot.auto.voice

/**
 * Listener for text-to-speech events.
 */
interface TextToSpeechListener {
    fun onSpeakingStarted(utteranceId: String)
    fun onSpeakingComplete(utteranceId: String)
    fun onError(utteranceId: String, errorCode: Int)
}

/**
 * Engine interface that abstracts Android TextToSpeech.
 * Production code creates an AndroidTtsEngine; tests supply a fake.
 */
interface TtsEngine {
    fun speak(text: String, utteranceId: String, listener: TextToSpeechListener)
    fun stop()
    fun shutdown()
    fun isAvailable(): Boolean
}

/**
 * Manages text-to-speech output for reading agent responses aloud.
 *
 * Supports sequential queueing: if [speak] or [enqueue] is called while
 * already speaking, the new text is queued and played after the current
 * utterance finishes.
 *
 * Usage:
 * ```
 * val tts = TextToSpeechManager(engine)
 * tts.listener = myListener
 * tts.speak("Hello from the lead agent")
 * ```
 */
class TextToSpeechManager(private val ttsEngine: TtsEngine) {

    companion object {
        const val TAG = "VanPilotTTS"
    }

    /** External listener for TTS events. */
    var listener: TextToSpeechListener? = null

    /** Whether the TTS engine is currently speaking. */
    var isSpeaking: Boolean = false
        private set

    /** Number of utterances waiting in the queue. */
    val queueSize: Int
        get() = pendingQueue.size

    private var utteranceCounter: Int = 0
    private val pendingQueue = mutableListOf<Pair<String, String>>() // (text, utteranceId)

    /**
     * Speak text immediately via the engine. Does not clear the queue —
     * queued items will still play after this utterance completes.
     * @return the utterance ID assigned to this text.
     */
    fun speak(text: String): String {
        val utteranceId = nextUtteranceId()
        isSpeaking = true
        ttsEngine.speak(text, utteranceId, internalListener)
        return utteranceId
    }

    /**
     * Add text to the queue. If not currently speaking, speaks immediately.
     * If already speaking, the text is enqueued and will play when the
     * current utterance finishes.
     * @return the utterance ID assigned to this text. The same ID will be
     *         passed to [TextToSpeechListener] callbacks when this item plays.
     */
    fun enqueue(text: String): String {
        val utteranceId = nextUtteranceId()
        if (isSpeaking) {
            pendingQueue.add(text to utteranceId)
        } else {
            isSpeaking = true
            ttsEngine.speak(text, utteranceId, internalListener)
        }
        return utteranceId
    }

    /**
     * Stop speaking and clear the queue.
     */
    fun stop() {
        pendingQueue.clear()
        isSpeaking = false
        ttsEngine.stop()
    }

    /**
     * Release all resources. Must be called when no longer needed.
     */
    fun destroy() {
        stop()
        ttsEngine.shutdown()
    }

    private fun nextUtteranceId(): String = "vp_${++utteranceCounter}"

    /**
     * Internal listener that manages the queue and forwards events
     * to the external [listener].
     */
    private val internalListener = object : TextToSpeechListener {
        override fun onSpeakingStarted(utteranceId: String) {
            listener?.onSpeakingStarted(utteranceId)
        }

        override fun onSpeakingComplete(utteranceId: String) {
            if (pendingQueue.isNotEmpty()) {
                val (nextText, nextId) = pendingQueue.removeAt(0)
                ttsEngine.speak(nextText, nextId, this)
            } else {
                isSpeaking = false
            }
            listener?.onSpeakingComplete(utteranceId)
        }

        override fun onError(utteranceId: String, errorCode: Int) {
            isSpeaking = false
            pendingQueue.clear()
            listener?.onError(utteranceId, errorCode)
        }
    }
}
