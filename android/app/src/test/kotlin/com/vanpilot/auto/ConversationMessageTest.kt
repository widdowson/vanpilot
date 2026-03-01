package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for ConversationMessage data class.
 */
@RunWith(JUnit4::class)
class ConversationMessageTest {

    @Test
    fun create_withAllFields() {
        val msg = ConversationMessage(
            sender = "lead-agent",
            text = "Hello from the lead agent",
            timestampMs = 1000L
        )
        assertThat(msg.sender).isEqualTo("lead-agent")
        assertThat(msg.text).isEqualTo("Hello from the lead agent")
        assertThat(msg.timestampMs).isEqualTo(1000L)
    }

    @Test
    fun equality_sameFields() {
        val msg1 = ConversationMessage("agent", "text", 100L)
        val msg2 = ConversationMessage("agent", "text", 100L)
        assertThat(msg1).isEqualTo(msg2)
    }

    @Test
    fun equality_differentFields() {
        val msg1 = ConversationMessage("agent1", "text", 100L)
        val msg2 = ConversationMessage("agent2", "text", 100L)
        assertThat(msg1).isNotEqualTo(msg2)
    }

    @Test
    fun copy_changesField() {
        val original = ConversationMessage("agent", "old text", 100L)
        val copied = original.copy(text = "new text")
        assertThat(copied.text).isEqualTo("new text")
        assertThat(copied.sender).isEqualTo("agent")
        assertThat(copied.timestampMs).isEqualTo(100L)
    }
}
