package com.vanpilot.auto.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.util.Locale

/**
 * Real [SttEngine] implementation wrapping Android's [SpeechRecognizer].
 * Uses offline language pack (no cloud API).
 */
class SttManager(private val context: Context) : SttEngine {

    private var recognizer: SpeechRecognizer? = null
    @Volatile private var _isListening = false

    override val isListening: Boolean get() = _isListening

    override fun startListening(
        locale: Locale,
        enablePartialResults: Boolean,
        onResult: (String) -> Unit,
        onPartialResult: (String) -> Unit,
        onError: (Int) -> Unit
    ) {
        val rec = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = rec

        rec.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val text = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull() ?: ""
                _isListening = false
                onResult(text)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                if (!enablePartialResults) return
                val text = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull() ?: ""
                onPartialResult(text)
            }

            override fun onError(error: Int) {
                _isListening = false
                onError(error)
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, locale.toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, enablePartialResults)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        }

        _isListening = true
        rec.startListening(intent)
    }

    override fun stopListening() {
        _isListening = false
        recognizer?.stopListening()
    }

    override fun destroy() {
        _isListening = false
        recognizer?.destroy()
        recognizer = null
    }
}
