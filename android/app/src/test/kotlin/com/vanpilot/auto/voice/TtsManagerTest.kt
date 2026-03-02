package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for [TtsManager].
 *
 * TtsManager wraps Android's TextToSpeech which cannot be instantiated
 * on host JVM. These tests verify class structure and interface compliance.
 * Behavioral TTS testing is done via [FakeTtsEngine] in [VoiceStateMachineTest].
 */
@RunWith(JUnit4::class)
class TtsManagerTest {

    @Test
    fun implementsTtsEngine() {
        assertThat(TtsEngine::class.java.isAssignableFrom(TtsManager::class.java)).isTrue()
    }

    @Test
    fun speakMethodExists() {
        val method = TtsManager::class.java.getMethod("speak", String::class.java)
        assertThat(method).isNotNull()
    }

    @Test
    fun stopMethodExists() {
        val method = TtsManager::class.java.getMethod("stop")
        assertThat(method).isNotNull()
    }

    @Test
    fun shutdownMethodExists() {
        val method = TtsManager::class.java.getMethod("shutdown")
        assertThat(method).isNotNull()
    }

    @Test
    fun isSpeakingPropertyExists() {
        val method = TtsManager::class.java.getMethod("isSpeaking")
        assertThat(method).isNotNull()
        assertThat(method.returnType).isEqualTo(Boolean::class.java)
    }

    @Test
    fun setOnUtteranceCompletedMethodExists() {
        val methods = TtsManager::class.java.methods.filter {
            it.name == "setOnUtteranceCompleted"
        }
        assertThat(methods).isNotEmpty()
    }

    @Test
    fun hasSpeechRateProperty() {
        val getter = TtsManager::class.java.getMethod("getSpeechRate")
        assertThat(getter).isNotNull()
        assertThat(getter.returnType).isEqualTo(Float::class.java)
    }

    @Test
    fun hasPitchProperty() {
        val getter = TtsManager::class.java.getMethod("getPitch")
        assertThat(getter).isNotNull()
        assertThat(getter.returnType).isEqualTo(Float::class.java)
    }

    @Test
    fun isSpeakingBackingField_isVolatile() {
        val field = TtsManager::class.java.getDeclaredField("_isSpeaking")
        assertThat(java.lang.reflect.Modifier.isVolatile(field.modifiers)).isTrue()
    }
}
