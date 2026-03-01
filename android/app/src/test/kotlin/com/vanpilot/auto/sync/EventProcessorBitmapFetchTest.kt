package com.vanpilot.auto.sync

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.cache.BitmapFetcher
import com.vanpilot.proto.v1.BitmapPayload
import com.vanpilot.proto.v1.DisplayCommand
import com.vanpilot.proto.v1.Event
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for auto-fetching missing bitmaps via BitmapFetcher (AC-7.2).
 */
@RunWith(JUnit4::class)
class EventProcessorBitmapFetchTest {

    private lateinit var cache: BitmapCache
    private val fetchedKeys = mutableListOf<String>()
    private val fetchResponses = mutableMapOf<String, ByteArray?>()

    private val fakeFetcher = BitmapFetcher { cacheKey ->
        fetchedKeys.add(cacheKey)
        fetchResponses[cacheKey]
    }

    private lateinit var processor: EventProcessor

    @Before
    fun setUp() {
        cache = BitmapCache(maxSize = 16)
        fetchedKeys.clear()
        fetchResponses.clear()
        processor = EventProcessor(cache, fakeFetcher)
    }

    @Test
    fun displayCommand_missingKey_triggersFetch() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        fetchResponses["0xMISSING"] = pngData

        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xMISSING")
            )
            .build()

        processor.processEvent(event)

        assertThat(fetchedKeys).containsExactly("0xMISSING")
        assertThat(cache.contains("0xMISSING")).isTrue()
        assertThat(cache.get("0xMISSING")).isEqualTo(pngData)
        assertThat(processor.currentDisplayKey).isEqualTo("0xMISSING")
    }

    @Test
    fun displayCommand_presentKey_doesNotFetch() {
        cache.put("0xEXISTS", byteArrayOf(1, 2, 3))

        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xEXISTS")
            )
            .build()

        processor.processEvent(event)

        assertThat(fetchedKeys).isEmpty()
        assertThat(processor.currentDisplayKey).isEqualTo("0xEXISTS")
    }

    @Test
    fun displayCommand_fetchReturnsNull_keyStillSet() {
        fetchResponses["0xGONE"] = null

        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xGONE")
            )
            .build()

        processor.processEvent(event)

        assertThat(fetchedKeys).containsExactly("0xGONE")
        assertThat(cache.contains("0xGONE")).isFalse()
        // Display key is still set even if fetch failed
        assertThat(processor.currentDisplayKey).isEqualTo("0xGONE")
    }

    @Test
    fun displayCommand_noFetcher_doesNotCrash() {
        val processorNoFetcher = EventProcessor(cache)

        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xNOFETCH")
            )
            .build()

        processorNoFetcher.processEvent(event)

        assertThat(processorNoFetcher.currentDisplayKey).isEqualTo("0xNOFETCH")
        assertThat(cache.contains("0xNOFETCH")).isFalse()
    }

    @Test
    fun fetchCount_tracksAutoFetches() {
        fetchResponses["0xA"] = byteArrayOf(1)
        fetchResponses["0xB"] = byteArrayOf(2)

        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setDisplayCommand(DisplayCommand.newBuilder().setCacheKey("0xA"))
                .build()
        )
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(2000)
                .setDisplayCommand(DisplayCommand.newBuilder().setCacheKey("0xB"))
                .build()
        )

        assertThat(processor.fetchCount).isEqualTo(2)
    }

    @Test
    fun bitmapPayloadThenDisplay_noFetchNeeded() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)

        // First receive bitmap payload
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setBitmapPayload(
                    BitmapPayload.newBuilder()
                        .setCacheKey("0xPRELOAD")
                        .setImageData(ByteString.copyFrom(pngData))
                )
                .build()
        )

        // Then display command — should not trigger fetch
        processor.processEvent(
            Event.newBuilder()
                .setTimestampMs(2000)
                .setDisplayCommand(
                    DisplayCommand.newBuilder().setCacheKey("0xPRELOAD")
                )
                .build()
        )

        assertThat(fetchedKeys).isEmpty()
        assertThat(processor.fetchCount).isEqualTo(0)
        assertThat(processor.currentDisplayKey).isEqualTo("0xPRELOAD")
    }
}
