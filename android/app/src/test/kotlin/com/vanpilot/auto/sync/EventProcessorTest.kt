package com.vanpilot.auto.sync

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.BitmapPayload
import com.vanpilot.proto.v1.DisplayCommand
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.InputDeliveryFailure
import com.vanpilot.proto.v1.TextMessage
import com.vanpilot.proto.v1.WatchdogTimeout
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class EventProcessorTest {

    private lateinit var cache: BitmapCache
    private lateinit var processor: EventProcessor

    @Before
    fun setUp() {
        cache = BitmapCache(maxSize = 16)
        processor = EventProcessor(cache)
    }

    @Test
    fun processTextMessage_storesMessage() {
        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setTextMessage(
                TextMessage.newBuilder()
                    .setAgentId("lead")
                    .setContent("Hello from agent")
            )
            .build()

        processor.processEvent(event)

        assertThat(processor.textMessages).hasSize(1)
        val msg = processor.textMessages[0]
        assertThat(msg.agentId).isEqualTo("lead")
        assertThat(msg.content).isEqualTo("Hello from agent")
        assertThat(msg.timestampMs).isEqualTo(1000)
    }

    @Test
    fun processBitmapPayload_storesInCache() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        val event = Event.newBuilder()
            .setTimestampMs(2000)
            .setBitmapPayload(
                BitmapPayload.newBuilder()
                    .setCacheKey("0xCAFE")
                    .setImageData(ByteString.copyFrom(pngData))
                    .setWidthPx(800)
                    .setHeightPx(480)
            )
            .build()

        processor.processEvent(event)

        assertThat(cache.contains("0xCAFE")).isTrue()
        assertThat(cache.get("0xCAFE")).isEqualTo(pngData)
    }

    @Test
    fun processDisplayCommand_updatesCurrentDisplayKey() {
        val event = Event.newBuilder()
            .setTimestampMs(3000)
            .setDisplayCommand(
                DisplayCommand.newBuilder()
                    .setCacheKey("0xBEEF")
            )
            .build()

        processor.processEvent(event)

        assertThat(processor.currentDisplayKey).isEqualTo("0xBEEF")
    }

    @Test
    fun processDisplayCommand_overwritesPreviousKey() {
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setDisplayCommand(DisplayCommand.newBuilder().setCacheKey("first"))
                .build()
        )
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(2000)
                .setDisplayCommand(DisplayCommand.newBuilder().setCacheKey("second"))
                .build()
        )

        assertThat(processor.currentDisplayKey).isEqualTo("second")
    }

    @Test
    fun processWatchdogTimeout_storesAlert() {
        val event = Event.newBuilder()
            .setTimestampMs(4000)
            .setWatchdogTimeout(
                WatchdogTimeout.newBuilder()
                    .setAgentId("researcher")
                    .setSilentDurationMs(30000)
            )
            .build()

        processor.processEvent(event)

        assertThat(processor.alerts).hasSize(1)
        val alert = processor.alerts[0]
        assertThat(alert.type).isEqualTo(AlertType.WATCHDOG_TIMEOUT)
        assertThat(alert.message).contains("researcher")
        assertThat(alert.message).contains("30000")
        assertThat(alert.timestampMs).isEqualTo(4000)
    }

    @Test
    fun processInputDeliveryFailure_storesAlert() {
        val event = Event.newBuilder()
            .setTimestampMs(5000)
            .setInputDeliveryFailure(
                InputDeliveryFailure.newBuilder()
                    .setAttemptedInput("deploy the app")
                    .setTargetAgentId("lead")
            )
            .build()

        processor.processEvent(event)

        assertThat(processor.alerts).hasSize(1)
        val alert = processor.alerts[0]
        assertThat(alert.type).isEqualTo(AlertType.INPUT_DELIVERY_FAILURE)
        assertThat(alert.message).contains("deploy the app")
        assertThat(alert.message).contains("lead")
        assertThat(alert.timestampMs).isEqualTo(5000)
    }

    @Test
    fun processEvents_handlesMultipleEvents() {
        val events = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setTextMessage(
                    TextMessage.newBuilder().setAgentId("lead").setContent("msg1")
                )
                .build(),
            Event.newBuilder()
                .setTimestampMs(2000)
                .setTextMessage(
                    TextMessage.newBuilder().setAgentId("lead").setContent("msg2")
                )
                .build(),
            Event.newBuilder()
                .setTimestampMs(3000)
                .setDisplayCommand(
                    DisplayCommand.newBuilder().setCacheKey("0xABC")
                )
                .build()
        )

        processor.processEvents(events)

        assertThat(processor.textMessages).hasSize(2)
        assertThat(processor.currentDisplayKey).isEqualTo("0xABC")
    }

    @Test
    fun initialState_noMessagesOrAlerts() {
        assertThat(processor.textMessages).isEmpty()
        assertThat(processor.alerts).isEmpty()
        assertThat(processor.currentDisplayKey).isNull()
    }
}
