package com.vanpilot.auto.sync

import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.Event
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class EventProcessorUnknownEventTest {

    private lateinit var cache: BitmapCache
    private lateinit var processor: EventProcessor

    @Before
    fun setUp() {
        cache = BitmapCache(maxSize = 16)
        processor = EventProcessor(cache)
    }

    @Test
    fun processEvent_unknownType_incrementsCounter() {
        // An Event with no payload set (default instance) is "unknown"
        val emptyEvent = Event.newBuilder()
            .setTimestampMs(9999)
            .build()

        processor.processEvent(emptyEvent)

        assertThat(processor.unknownEventCount).isEqualTo(1)
    }

    @Test
    fun processEvent_unknownType_doesNotCrash() {
        val emptyEvent = Event.newBuilder()
            .setTimestampMs(1000)
            .build()

        // Should not throw
        processor.processEvent(emptyEvent)

        // State should be unaffected
        assertThat(processor.textMessages).isEmpty()
        assertThat(processor.alerts).isEmpty()
        assertThat(processor.currentDisplayKey).isNull()
    }

    @Test
    fun processEvents_multipleUnknown_countsAll() {
        val events = (1..3).map { i ->
            Event.newBuilder()
                .setTimestampMs(i.toLong() * 1000)
                .build()
        }

        processor.processEvents(events)

        assertThat(processor.unknownEventCount).isEqualTo(3)
    }

    @Test
    fun processEvent_knownType_doesNotIncrementUnknownCounter() {
        val textEvent = Event.newBuilder()
            .setTimestampMs(1000)
            .setTextMessage(
                com.vanpilot.proto.v1.TextMessage.newBuilder()
                    .setAgentId("lead")
                    .setContent("hello")
            )
            .build()

        processor.processEvent(textEvent)

        assertThat(processor.unknownEventCount).isEqualTo(0)
    }
}
