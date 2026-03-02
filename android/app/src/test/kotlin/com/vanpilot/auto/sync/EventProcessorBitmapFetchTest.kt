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
 * Tests for async bitmap fetching via BitmapFetcher (AC-7.2, #57).
 *
 * When a DisplayCommand references a missing cache key, the processor
 * queues a pending fetch. The caller retrieves the data asynchronously
 * and calls completeFetch() when it arrives.
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
    fun displayCommand_missingKey_queuesFetchAndCachesOnComplete() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)

        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xMISSING")
            )
            .build()

        processor.processEvent(event)

        // Fetch is queued, not executed synchronously
        assertThat(processor.pendingFetches).containsExactly("0xMISSING")
        assertThat(fetchedKeys).isEmpty()
        assertThat(processor.currentDisplayKey).isEqualTo("0xMISSING")

        // Simulate async fetch completion
        processor.completeFetch("0xMISSING", pngData)

        assertThat(cache.contains("0xMISSING")).isTrue()
        assertThat(cache.get("0xMISSING")).isEqualTo(pngData)
        assertThat(processor.pendingFetches).isEmpty()
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

        assertThat(processor.pendingFetches).isEmpty()
        assertThat(processor.currentDisplayKey).isEqualTo("0xEXISTS")
    }

    @Test
    fun displayCommand_fetchReturnsNull_keyStillSet() {
        val event = Event.newBuilder()
            .setTimestampMs(1000)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey("0xGONE")
            )
            .build()

        processor.processEvent(event)

        assertThat(processor.pendingFetches).containsExactly("0xGONE")
        // Display key is set immediately even before fetch completes
        assertThat(processor.currentDisplayKey).isEqualTo("0xGONE")

        // Simulate async fetch returning null (failure)
        processor.completeFetch("0xGONE", null)

        assertThat(cache.contains("0xGONE")).isFalse()
        assertThat(processor.pendingFetches).isEmpty()
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
        assertThat(processorNoFetcher.pendingFetches).isEmpty()
        assertThat(cache.contains("0xNOFETCH")).isFalse()
    }

    @Test
    fun fetchCount_tracksCompletedFetches() {
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

        assertThat(processor.pendingFetches).containsExactly("0xA", "0xB")

        // Complete both fetches
        processor.completeFetch("0xA", byteArrayOf(1))
        processor.completeFetch("0xB", byteArrayOf(2))

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

        assertThat(processor.pendingFetches).isEmpty()
        assertThat(processor.fetchCount).isEqualTo(0)
        assertThat(processor.currentDisplayKey).isEqualTo("0xPRELOAD")
    }
}
