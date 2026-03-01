package com.vanpilot.auto.voice

import android.content.Context
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/**
 * Real [TtsEngine] implementation wrapping Android's [TextToSpeech].
 * Uses the device's built-in TTS engine (no cloud API).
 */
class TtsManager(context: Context) : TtsEngine {

    private var tts: TextToSpeech? = null
    private var initialized = false
    private var _isSpeaking = false
    private var onUtteranceCompleted: (() -> Unit)? = null

    /** Speech rate multiplier (1.0 = normal). */
    var speechRate: Float = 1.0f
        set(value) {
            field = value
            tts?.setSpeechRate(value)
        }

    /** Pitch multiplier (1.0 = normal). */
    var pitch: Float = 1.0f
        set(value) {
            field = value
            tts?.setPitch(value)
        }

    /** Language locale for TTS output. */
    var locale: Locale = Locale.US
        set(value) {
            field = value
            tts?.language = value
        }

    private val progressListener = object : UtteranceProgressListener() {
        override fun onDone(uid: String?) {
            _isSpeaking = false
            onUtteranceCompleted?.invoke()
        }

        override fun onError(uid: String?) {
            _isSpeaking = false
        }

        override fun onStart(uid: String?) {}
    }

    init {
        tts = TextToSpeech(context) { status ->
            initialized = status == TextToSpeech.SUCCESS
            if (initialized) {
                tts?.language = locale
                tts?.setSpeechRate(speechRate)
                tts?.setPitch(pitch)
                tts?.setOnUtteranceProgressListener(progressListener)
            }
        }
    }

    override val isSpeaking: Boolean get() = _isSpeaking

    /**
     * Speak the given text using QUEUE_FLUSH — any in-progress utterance
     * is stopped and replaced by [text].
     */
    override fun speak(text: String) {
        if (!initialized) return
        _isSpeaking = true
        val utteranceId = System.currentTimeMillis().toString()
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, Bundle(), utteranceId)
    }

    override fun stop() {
        _isSpeaking = false
        tts?.stop()
    }

    override fun shutdown() {
        _isSpeaking = false
        tts?.stop()
        tts?.shutdown()
        tts = null
        initialized = false
    }

    override fun setOnUtteranceCompleted(callback: (() -> Unit)?) {
        onUtteranceCompleted = callback
    }
}
