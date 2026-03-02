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
 * Tests for async bitmap fetching in EventProcessor (#57).
 *
 * When a DisplayCommand references a missing cache key, the processor
 * should NOT block the event processing loop. Instead it queues a
 * pending fetch that the caller processes asynchronously.
 */
@RunWith(JUnit4::class)
class EventProcessorAsyncFetchTest {

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

    private fun displayEvent(key: String, ts: Long = 1000): Event =
        Event.newBuilder()
            .setTimestampMs(ts)
            .setDisplayCommand(DisplayCommand.newBuilder().setCacheKey(key))
            .build()

    @Test
    fun missingBitmap_queuesPendingFetch() {
        processor.processEvent(displayEvent("0xMISSING"))

        assertThat(processor.pendingFetches).containsExactly("0xMISSING")
    }

    @Test
    fun missingBitmap_doesNotCallFetcherSynchronously() {
        processor.processEvent(displayEvent("0xMISSING"))

        // The fetcher should NOT have been called during processEvent
        assertThat(fetchedKeys).isEmpty()
    }

    @Test
    fun missingBitmap_setsDisplayKeyImmediately() {
        processor.processEvent(displayEvent("0xMISSING"))

        assertThat(processor.currentDisplayKey).isEqualTo("0xMISSING")
    }

    @Test
    fun presentBitmap_noPendingFetch() {
        cache.put("0xEXISTS", byteArrayOf(1, 2, 3))

        processor.processEvent(displayEvent("0xEXISTS"))

        assertThat(processor.pendingFetches).isEmpty()
    }

    @Test
    fun completeFetch_putsDataInCache() {
        processor.processEvent(displayEvent("0xMISSING"))

        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        processor.completeFetch("0xMISSING", pngData)

        assertThat(cache.contains("0xMISSING")).isTrue()
        assertThat(cache.get("0xMISSING")).isEqualTo(pngData)
    }

    @Test
    fun completeFetch_removesPendingEntry() {
        processor.processEvent(displayEvent("0xMISSING"))
        assertThat(processor.pendingFetches).hasSize(1)

        processor.completeFetch("0xMISSING", byteArrayOf(1))

        assertThat(processor.pendingFetches).isEmpty()
    }

    @Test
    fun completeFetch_incrementsFetchCount() {
        processor.processEvent(displayEvent("0xMISSING"))
        processor.completeFetch("0xMISSING", byteArrayOf(1))

        assertThat(processor.fetchCount).isEqualTo(1)
    }

    @Test
    fun completeFetch_nullData_removesWithoutCaching() {
        processor.processEvent(displayEvent("0xGONE"))
        processor.completeFetch("0xGONE", null)

        assertThat(processor.pendingFetches).isEmpty()
        assertThat(cache.contains("0xGONE")).isFalse()
        assertThat(processor.fetchCount).isEqualTo(0)
    }

    @Test
    fun multiplePendingFetches_trackedIndependently() {
        processor.processEvent(displayEvent("0xA", ts = 1000))
        processor.processEvent(displayEvent("0xB", ts = 2000))

        assertThat(processor.pendingFetches).containsExactly("0xA", "0xB")

        processor.completeFetch("0xA", byteArrayOf(1))
        assertThat(processor.pendingFetches).containsExactly("0xB")
    }

    @Test
    fun duplicateDisplayCommand_doesNotDuplicatePending() {
        processor.processEvent(displayEvent("0xSAME", ts = 1000))
        processor.processEvent(displayEvent("0xSAME", ts = 2000))

        // Should not have duplicate pending entries
        assertThat(processor.pendingFetches).containsExactly("0xSAME")
    }

    @Test
    fun noFetcher_noPendingFetch() {
        val processorNoFetcher = EventProcessor(cache)

        processorNoFetcher.processEvent(displayEvent("0xNOFETCH"))

        assertThat(processorNoFetcher.pendingFetches).isEmpty()
        assertThat(processorNoFetcher.currentDisplayKey).isEqualTo("0xNOFETCH")
    }

    @Test
    fun bitmapPayloadThenDisplay_noPendingFetch() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
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

        processor.processEvent(displayEvent("0xPRELOAD", ts = 2000))

        assertThat(processor.pendingFetches).isEmpty()
        assertThat(processor.fetchCount).isEqualTo(0)
    }
}
