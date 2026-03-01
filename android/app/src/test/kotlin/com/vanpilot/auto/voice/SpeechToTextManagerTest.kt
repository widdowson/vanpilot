package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for SpeechToTextManager.
 * Uses a fake SpeechRecognizerFactory to test without the Android runtime.
 */
@RunWith(JUnit4::class)
class SpeechToTextManagerTest {

    private lateinit var manager: SpeechToTextManager
    private lateinit var fakeFactory: FakeSpeechRecognizerFactory
    private lateinit var results: MutableList<String>
    private lateinit var errors: MutableList<Pair<Int, String>>

    @Before
    fun setUp() {
        fakeFactory = FakeSpeechRecognizerFactory()
        manager = SpeechToTextManager(fakeFactory)
        results = mutableListOf()
        errors = mutableListOf()
        manager.listener = object : SpeechToTextListener {
            override fun onResult(text: String) { results.add(text) }
            override fun onPartialResult(text: String) {}
            override fun onError(errorCode: Int, message: String) { errors.add(errorCode to message) }
            override fun onReadyForSpeech() {}
            override fun onEndOfSpeech() {}
        }
    }

    // --- Initial state ---

    @Test
    fun initialState_notListening() {
        assertThat(manager.isListening).isFalse()
    }

    @Test
    fun tag_isCorrect() {
        assertThat(SpeechToTextManager.TAG).isEqualTo("VanPilotSTT")
    }

    // --- Start listening ---

    @Test
    fun startListening_setsListeningTrue() {
        val result = manager.startListening()
        assertThat(result).isTrue()
        assertThat(manager.isListening).isTrue()
    }

    @Test
    fun startListening_delegatesToFactory() {
        manager.startListening()
        assertThat(fakeFactory.isRecognizing).isTrue()
    }

    @Test
    fun startListening_whileAlreadyListening_returnsFalse() {
        manager.startListening()
        val result = manager.startListening()
        assertThat(result).isFalse()
    }

    // --- Stop listening ---

    @Test
    fun stopListening_setsListeningFalse() {
        manager.startListening()
        manager.stopListening()
        assertThat(manager.isListening).isFalse()
    }

    @Test
    fun stopListening_delegatesToFactory() {
        manager.startListening()
        manager.stopListening()
        assertThat(fakeFactory.isRecognizing).isFalse()
    }

    @Test
    fun stopListening_whenNotListening_noOp() {
        manager.stopListening()
        assertThat(manager.isListening).isFalse()
    }

    // --- Recognition results ---

    @Test
    fun onResult_fromFactory_delegatesToListener() {
        manager.startListening()
        fakeFactory.simulateResult("hello world")
        assertThat(results).containsExactly("hello world")
    }

    @Test
    fun onResult_setsListeningFalse() {
        manager.startListening()
        fakeFactory.simulateResult("hello")
        assertThat(manager.isListening).isFalse()
    }

    // --- Recognition errors ---

    @Test
    fun onError_fromFactory_delegatesToListener() {
        manager.startListening()
        fakeFactory.simulateError(7, "No match")
        assertThat(errors).containsExactly(7 to "No match")
    }

    @Test
    fun onError_setsListeningFalse() {
        manager.startListening()
        fakeFactory.simulateError(7, "No match")
        assertThat(manager.isListening).isFalse()
    }

    // --- Destroy ---

    @Test
    fun destroy_stopsListening() {
        manager.startListening()
        manager.destroy()
        assertThat(manager.isListening).isFalse()
    }

    @Test
    fun destroy_destroysFactory() {
        manager.destroy()
        assertThat(fakeFactory.isDestroyed).isTrue()
    }

    // --- Factory availability ---

    @Test
    fun factoryAvailable_delegatesToFactory() {
        fakeFactory.available = true
        assertThat(fakeFactory.isAvailable()).isTrue()
        fakeFactory.available = false
        assertThat(fakeFactory.isAvailable()).isFalse()
    }
}

/**
 * Fake implementation of SpeechRecognizerFactory for testing.
 */
class FakeSpeechRecognizerFactory : SpeechRecognizerFactory {
    var isRecognizing = false
        private set
    var isDestroyed = false
        private set
    var available = true

    private var activeListener: SpeechToTextListener? = null

    override fun startRecognition(listener: SpeechToTextListener) {
        isRecognizing = true
        activeListener = listener
    }

    override fun stopRecognition() {
        isRecognizing = false
        activeListener = null
    }

    override fun destroy() {
        isDestroyed = true
        isRecognizing = false
        activeListener = null
    }

    override fun isAvailable(): Boolean = available

    fun simulateResult(text: String) {
        activeListener?.onResult(text)
    }

    fun simulateError(errorCode: Int, message: String) {
        activeListener?.onError(errorCode, message)
    }

    fun simulatePartialResult(text: String) {
        activeListener?.onPartialResult(text)
    }
}
