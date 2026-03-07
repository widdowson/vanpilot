package com.vanpilot.auto.sync

import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.DisplayCommand
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.TextMessage
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests that EventProcessor fires the textMessageListener callback
 * when processing text message events.
 */
@RunWith(JUnit4::class)
class EventProcessorCallbackTest {

    private lateinit var cache: BitmapCache
    private lateinit var processor: EventProcessor

    @Before
    fun setUp() {
        cache = BitmapCache()
        processor = EventProcessor(cache)
    }

    @Test
    fun processEvent_textMessage_callsListener() {
        val received = mutableListOf<Triple<String, String, Long>>()
        processor.textMessageListener = { agentId, content, ts ->
            received.add(Triple(agentId, content, ts))
        }

        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000L)
                .setTextMessage(
                    TextMessage.newBuilder()
                        .setAgentId("lead")
                        .setContent("hello")
                )
                .build()
        )

        assertThat(received).hasSize(1)
        assertThat(received[0]).isEqualTo(Triple("lead", "hello", 1000L))
    }

    @Test
    fun processEvent_multipleTextMessages_callsListenerForEach() {
        var callCount = 0
        processor.textMessageListener = { _, _, _ -> callCount++ }

        processor.processEvents(listOf(
            Event.newBuilder()
                .setTimestampMs(1000L)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("a"))
                .build(),
            Event.newBuilder()
                .setTimestampMs(2000L)
                .setTextMessage(TextMessage.newBuilder().setAgentId("researcher").setContent("b"))
                .build()
        ))

        assertThat(callCount).isEqualTo(2)
    }

    @Test
    fun processEvent_nonTextMessage_doesNotCallListener() {
        var called = false
        processor.textMessageListener = { _, _, _ -> called = true }

        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000L)
                .setDisplayCommand(
                    DisplayCommand.newBuilder().setCacheKey("0xCAFE")
                )
                .build()
        )

        assertThat(called).isFalse()
    }

    @Test
    fun processEvent_noListener_doesNotThrow() {
        // No listener set — should not crash
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000L)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("hi"))
                .build()
        )

        // Verify message still stored internally
        assertThat(processor.textMessages).hasSize(1)
    }
}
