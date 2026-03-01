package com.vanpilot.auto.voice

import java.util.Locale

/**
 * Fake [SttEngine] for testing. Records calls and exposes
 * helpers to simulate STT callbacks.
 */
class FakeSttEngine : SttEngine {

    private var _isListening = false
    override val isListening: Boolean get() = _isListening

    var lastLocale: Locale? = null
    var lastEnablePartialResults: Boolean? = null
    var startCount = 0
    var stopCount = 0
    var destroyCount = 0

    private var onResult: ((String) -> Unit)? = null
    private var onPartialResult: ((String) -> Unit)? = null
    private var onError: ((Int) -> Unit)? = null

    override fun startListening(
        locale: Locale,
        enablePartialResults: Boolean,
        onResult: (String) -> Unit,
        onPartialResult: (String) -> Unit,
        onError: (Int) -> Unit
    ) {
        _isListening = true
        lastLocale = locale
        lastEnablePartialResults = enablePartialResults
        this.onResult = onResult
        this.onPartialResult = onPartialResult
        this.onError = onError
        startCount++
    }

    override fun stopListening() {
        _isListening = false
        stopCount++
    }

    override fun destroy() {
        _isListening = false
        destroyCount++
    }

    /** Simulate a final STT result. */
    fun simulateResult(text: String) {
        onResult?.invoke(text)
    }

    /** Simulate a partial STT result. */
    fun simulatePartialResult(text: String) {
        onPartialResult?.invoke(text)
    }

    /** Simulate an STT error. */
    fun simulateError(code: Int) {
        onError?.invoke(code)
    }
}
