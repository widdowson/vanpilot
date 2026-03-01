package com.vanpilot.auto.voice

/**
 * Fake [TtsEngine] for testing. Records calls and exposes
 * helpers to simulate TTS callbacks.
 */
class FakeTtsEngine : TtsEngine {

    private var _isSpeaking = false
    override val isSpeaking: Boolean get() = _isSpeaking

    var lastSpokenText: String? = null
    var speakCount = 0
    var stopCount = 0
    var shutdownCount = 0
    private var onCompleted: (() -> Unit)? = null

    override fun speak(text: String) {
        _isSpeaking = true
        lastSpokenText = text
        speakCount++
    }

    override fun stop() {
        _isSpeaking = false
        stopCount++
    }

    override fun shutdown() {
        _isSpeaking = false
        shutdownCount++
    }

    override fun setOnUtteranceCompleted(callback: (() -> Unit)?) {
        onCompleted = callback
    }

    /** Simulate TTS utterance completion. */
    fun simulateCompletion() {
        _isSpeaking = false
        onCompleted?.invoke()
    }
}
