package com.vanpilot.auto.voice

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for [SttManager].
 *
 * SttManager wraps Android's SpeechRecognizer which cannot be instantiated
 * on host JVM. These tests verify class structure and interface compliance.
 * Behavioral STT testing is done via [FakeSttEngine] in [VoiceStateMachineTest].
 */
@RunWith(JUnit4::class)
class SttManagerTest {

    @Test
    fun implementsSttEngine() {
        assertThat(SttEngine::class.java.isAssignableFrom(SttManager::class.java)).isTrue()
    }

    @Test
    fun startListeningMethodExists() {
        val methods = SttManager::class.java.methods.filter { it.name == "startListening" }
        assertThat(methods).isNotEmpty()
    }

    @Test
    fun stopListeningMethodExists() {
        val method = SttManager::class.java.getMethod("stopListening")
        assertThat(method).isNotNull()
    }

    @Test
    fun destroyMethodExists() {
        val method = SttManager::class.java.getMethod("destroy")
        assertThat(method).isNotNull()
    }

    @Test
    fun isListeningPropertyExists() {
        val method = SttManager::class.java.getMethod("isListening")
        assertThat(method).isNotNull()
        assertThat(method.returnType).isEqualTo(Boolean::class.java)
    }

    @Test
    fun isListeningBackingField_isVolatile() {
        val field = SttManager::class.java.getDeclaredField("_isListening")
        assertThat(java.lang.reflect.Modifier.isVolatile(field.modifiers)).isTrue()
    }
}
