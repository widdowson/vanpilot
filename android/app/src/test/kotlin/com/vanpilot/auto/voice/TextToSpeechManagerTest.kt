package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for TextToSpeechManager.
 * Uses a fake TtsEngine to test without the Android runtime.
 */
@RunWith(JUnit4::class)
class TextToSpeechManagerTest {

    private lateinit var manager: TextToSpeechManager
    private lateinit var fakeEngine: FakeTtsEngine
    private lateinit var completedUtterances: MutableList<String>
    private lateinit var errorUtterances: MutableList<String>

    @Before
    fun setUp() {
        fakeEngine = FakeTtsEngine()
        manager = TextToSpeechManager(fakeEngine)
        completedUtterances = mutableListOf()
        errorUtterances = mutableListOf()
        manager.listener = object : TextToSpeechListener {
            override fun onSpeakingStarted(utteranceId: String) {}
            override fun onSpeakingComplete(utteranceId: String) { completedUtterances.add(utteranceId) }
            override fun onError(utteranceId: String, errorCode: Int) { errorUtterances.add(utteranceId) }
        }
    }

    // --- Initial state ---

    @Test
    fun initialState_notSpeaking() {
        assertThat(manager.isSpeaking).isFalse()
    }

    @Test
    fun initialState_emptyQueue() {
        assertThat(manager.queueSize).isEqualTo(0)
    }

    @Test
    fun tag_isCorrect() {
        assertThat(TextToSpeechManager.TAG).isEqualTo("VanPilotTTS")
    }

    // --- Speak ---

    @Test
    fun speak_setsSpeakingTrue() {
        manager.speak("hello")
        assertThat(manager.isSpeaking).isTrue()
    }

    @Test
    fun speak_delegatesToEngine() {
        manager.speak("hello world")
        assertThat(fakeEngine.lastSpokenText).isEqualTo("hello world")
    }

    @Test
    fun speak_returnsUtteranceId() {
        val id = manager.speak("hello")
        assertThat(id).startsWith("vp_")
    }

    @Test
    fun speak_incrementsUtteranceId() {
        val id1 = manager.speak("first")
        fakeEngine.simulateComplete()
        val id2 = manager.speak("second")
        assertThat(id1).isNotEqualTo(id2)
    }

    // --- Speak completion ---

    @Test
    fun onSpeakingComplete_setsSpeakingFalse() {
        manager.speak("hello")
        fakeEngine.simulateComplete()
        assertThat(manager.isSpeaking).isFalse()
    }

    @Test
    fun onSpeakingComplete_notifiesListener() {
        val id = manager.speak("hello")
        fakeEngine.simulateComplete()
        assertThat(completedUtterances).containsExactly(id)
    }

    // --- Queue ---

    @Test
    fun enqueue_whileNotSpeaking_speaksImmediately() {
        manager.enqueue("hello")
        assertThat(manager.isSpeaking).isTrue()
        assertThat(fakeEngine.lastSpokenText).isEqualTo("hello")
        assertThat(manager.queueSize).isEqualTo(0)
    }

    @Test
    fun enqueue_whileSpeaking_addsToQueue() {
        manager.speak("first")
        manager.enqueue("second")
        assertThat(manager.queueSize).isEqualTo(1)
    }

    @Test
    fun enqueue_multipleWhileSpeaking_queuesAll() {
        manager.speak("first")
        manager.enqueue("second")
        manager.enqueue("third")
        assertThat(manager.queueSize).isEqualTo(2)
    }

    @Test
    fun queue_drainsOnCompletion() {
        manager.speak("first")
        manager.enqueue("second")
        manager.enqueue("third")

        // Complete first utterance - "second" should start speaking
        fakeEngine.simulateComplete()
        assertThat(manager.isSpeaking).isTrue()
        assertThat(fakeEngine.lastSpokenText).isEqualTo("second")
        assertThat(manager.queueSize).isEqualTo(1)

        // Complete second utterance - "third" should start speaking
        fakeEngine.simulateComplete()
        assertThat(manager.isSpeaking).isTrue()
        assertThat(fakeEngine.lastSpokenText).isEqualTo("third")
        assertThat(manager.queueSize).isEqualTo(0)

        // Complete third utterance - nothing left
        fakeEngine.simulateComplete()
        assertThat(manager.isSpeaking).isFalse()
    }

    // --- Stop ---

    @Test
    fun stop_setsSpeakingFalse() {
        manager.speak("hello")
        manager.stop()
        assertThat(manager.isSpeaking).isFalse()
    }

    @Test
    fun stop_clearsQueue() {
        manager.speak("first")
        manager.enqueue("second")
        manager.enqueue("third")
        manager.stop()
        assertThat(manager.queueSize).isEqualTo(0)
    }

    @Test
    fun stop_delegatesToEngine() {
        manager.speak("hello")
        manager.stop()
        assertThat(fakeEngine.isStopped).isTrue()
    }

    // --- Error handling ---

    @Test
    fun onError_setsSpeakingFalse() {
        manager.speak("hello")
        fakeEngine.simulateError(1)
        assertThat(manager.isSpeaking).isFalse()
    }

    @Test
    fun onError_clearsQueue() {
        manager.speak("first")
        manager.enqueue("second")
        fakeEngine.simulateError(1)
        assertThat(manager.queueSize).isEqualTo(0)
    }

    @Test
    fun onError_notifiesListener() {
        val id = manager.speak("hello")
        fakeEngine.simulateError(1)
        assertThat(errorUtterances).containsExactly(id)
    }

    // --- Destroy ---

    @Test
    fun destroy_stopsAndShutdown() {
        manager.speak("hello")
        manager.enqueue("world")
        manager.destroy()
        assertThat(manager.isSpeaking).isFalse()
        assertThat(manager.queueSize).isEqualTo(0)
        assertThat(fakeEngine.isShutdown).isTrue()
    }
}

/**
 * Fake implementation of TtsEngine for testing.
 */
class FakeTtsEngine : TtsEngine {
    var lastSpokenText: String? = null
        private set
    var lastUtteranceId: String? = null
        private set
    var isStopped = false
        private set
    var isShutdown = false
        private set

    private var activeListener: TextToSpeechListener? = null

    override fun speak(text: String, utteranceId: String, listener: TextToSpeechListener) {
        lastSpokenText = text
        lastUtteranceId = utteranceId
        activeListener = listener
        isStopped = false
    }

    override fun stop() {
        isStopped = true
        activeListener = null
    }

    override fun shutdown() {
        isShutdown = true
        isStopped = true
        activeListener = null
    }

    override fun isAvailable(): Boolean = !isShutdown

    fun simulateComplete() {
        val id = lastUtteranceId ?: return
        activeListener?.onSpeakingComplete(id)
    }

    fun simulateError(errorCode: Int) {
        val id = lastUtteranceId ?: return
        activeListener?.onError(id, errorCode)
    }
}
