package com.vanpilot.auto.sync

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.grpc.SyncServiceClient
import com.vanpilot.proto.v1.BitmapPayload
import com.vanpilot.proto.v1.DisplayCommand
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetBitmapResponse
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.SendUserInputRequest
import com.vanpilot.proto.v1.SendUserInputResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.TextMessage
import io.grpc.Server
import io.grpc.Status
import io.grpc.inprocess.InProcessChannelBuilder
import io.grpc.inprocess.InProcessServerBuilder
import io.grpc.stub.StreamObserver
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class SyncPollerTest {

    private lateinit var server: Server
    private lateinit var client: SyncServiceClient
    private lateinit var cache: BitmapCache
    private lateinit var processor: EventProcessor
    private lateinit var poller: SyncPoller
    private val fakeService = FakeSyncService()

    @Before
    fun setUp() {
        val serverName = InProcessServerBuilder.generateName()
        server = InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(fakeService)
            .build()
            .start()
        val channel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .build()
        client = SyncServiceClient(channel)
        cache = BitmapCache(maxSize = 16)
        processor = EventProcessor(cache)
        poller = SyncPoller(client, processor, cache)
    }

    @After
    fun tearDown() {
        client.shutdown()
        server.shutdownNow()
    }

    // ---- Adaptive batching: grow on success ----

    @Test
    fun batchSize_growsWhenFullBatchReturned() {
        val initial = poller.batchSize
        // Return exactly batchSize events to signal "more available"
        fakeService.eventsToReturn = makeTextEvents(initial)

        poller.pollOnce()

        assertThat(poller.batchSize).isEqualTo(initial * 2)
    }

    @Test
    fun batchSize_doesNotGrowOnPartialBatch() {
        val initial = poller.batchSize
        // Return fewer events than batchSize
        fakeService.eventsToReturn = makeTextEvents(initial - 1)

        poller.pollOnce()

        assertThat(poller.batchSize).isEqualTo(initial)
    }

    @Test
    fun batchSize_cappedAtMax() {
        // Force batch size to just below max
        repeat(20) {
            fakeService.eventsToReturn = makeTextEvents(poller.batchSize)
            poller.pollOnce()
        }

        assertThat(poller.batchSize).isEqualTo(SyncPoller.MAX_BATCH_SIZE)
    }

    // ---- Adaptive batching: shrink on error ----

    @Test
    fun batchSize_shrinksOnError() {
        // First grow it
        fakeService.eventsToReturn = makeTextEvents(poller.batchSize)
        poller.pollOnce()
        val grown = poller.batchSize

        // Now cause an error
        fakeService.failNextGetEvents = true
        poller.pollOnce()

        assertThat(poller.batchSize).isEqualTo(grown / 2)
    }

    @Test
    fun batchSize_flooredAtMin() {
        // Shrink repeatedly
        repeat(20) {
            fakeService.failNextGetEvents = true
            poller.pollOnce()
        }

        assertThat(poller.batchSize).isEqualTo(SyncPoller.MIN_BATCH_SIZE)
    }

    @Test
    fun pollOnce_returnsZeroOnError() {
        fakeService.failNextGetEvents = true

        val count = poller.pollOnce()

        assertThat(count).isEqualTo(0)
    }

    // ---- Timestamp progression ----

    @Test
    fun sinceTimestampMs_advancesToLastEventTimestamp() {
        fakeService.eventsToReturn = listOf(
            textEvent("a", "msg1", timestampMs = 1000),
            textEvent("a", "msg2", timestampMs = 2000),
            textEvent("a", "msg3", timestampMs = 3000)
        )

        poller.pollOnce()

        assertThat(poller.sinceTimestampMs).isEqualTo(3000)
    }

    @Test
    fun sinceTimestampMs_passedToNextPoll() {
        fakeService.eventsToReturn = listOf(textEvent("a", "msg", timestampMs = 5000))
        poller.pollOnce()

        // Second poll should use updated timestamp
        fakeService.eventsToReturn = emptyList()
        poller.pollOnce()

        assertThat(fakeService.lastGetEventsRequest?.sinceTimestampMs).isEqualTo(5000)
    }

    @Test
    fun sinceTimestampMs_unchangedOnEmptyResponse() {
        fakeService.eventsToReturn = emptyList()

        poller.pollOnce()

        assertThat(poller.sinceTimestampMs).isEqualTo(0)
    }

    // ---- resetSync ----

    @Test
    fun resetSync_resetsTimestampAndBatchSize() {
        // Advance state
        fakeService.eventsToReturn = makeTextEvents(poller.batchSize)
        poller.pollOnce()
        assertThat(poller.sinceTimestampMs).isGreaterThan(0)
        assertThat(poller.batchSize).isGreaterThan(SyncPoller.INITIAL_BATCH_SIZE)

        poller.resetSync()

        assertThat(poller.sinceTimestampMs).isEqualTo(0)
        assertThat(poller.batchSize).isEqualTo(SyncPoller.INITIAL_BATCH_SIZE)
    }

    // ---- DisplayCommand: null guard when bitmap missing ----

    @Test
    fun displayCommand_dispatchedWhenBitmapInCache() {
        cache.put("0xCAFE", byteArrayOf(1, 2, 3))
        fakeService.eventsToReturn = listOf(displayEvent("0xCAFE", timestampMs = 1000))
        val dispatched = mutableListOf<String>()
        poller.onDisplayCommand = { dispatched.add(it) }

        poller.pollOnce()

        assertThat(dispatched).containsExactly("0xCAFE")
    }

    @Test
    fun displayCommand_fetchesMissingBitmapThenDispatches() {
        // Bitmap NOT in cache, but GetBitmap RPC will return it
        fakeService.bitmapToReturn = BitmapPayload.newBuilder()
            .setCacheKey("0xBEEF")
            .setImageData(ByteString.copyFrom(byteArrayOf(0x89.toByte(), 0x50)))
            .build()
        fakeService.eventsToReturn = listOf(displayEvent("0xBEEF", timestampMs = 1000))
        val dispatched = mutableListOf<String>()
        poller.onDisplayCommand = { dispatched.add(it) }

        poller.pollOnce()

        assertThat(dispatched).containsExactly("0xBEEF")
        assertThat(cache.contains("0xBEEF")).isTrue()
    }

    @Test
    fun displayCommand_skippedWhenGetBitmapFails() {
        // Bitmap NOT in cache, and GetBitmap RPC will fail
        fakeService.failNextGetBitmap = true
        fakeService.eventsToReturn = listOf(displayEvent("0xDEAD", timestampMs = 1000))
        val dispatched = mutableListOf<String>()
        poller.onDisplayCommand = { dispatched.add(it) }

        poller.pollOnce()

        assertThat(dispatched).isEmpty()
    }

    @Test
    fun displayCommand_skippedWhenGetBitmapReturnsEmptyData() {
        // GetBitmap returns empty image data
        fakeService.bitmapToReturn = BitmapPayload.newBuilder()
            .setCacheKey("0xBAD")
            .setImageData(ByteString.EMPTY)
            .build()
        fakeService.eventsToReturn = listOf(displayEvent("0xBAD", timestampMs = 1000))
        val dispatched = mutableListOf<String>()
        poller.onDisplayCommand = { dispatched.add(it) }

        poller.pollOnce()

        assertThat(dispatched).isEmpty()
    }

    // ---- TextMessage callback ----

    @Test
    fun textMessage_callbackInvoked() {
        fakeService.eventsToReturn = listOf(textEvent("lead", "Hello!", timestampMs = 1000))
        val received = mutableListOf<Pair<String, String>>()
        poller.onTextMessage = { agent, content -> received.add(agent to content) }

        poller.pollOnce()

        assertThat(received).containsExactly("lead" to "Hello!")
    }

    @Test
    fun textMessage_multipleCallbacksInOrder() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "first", timestampMs = 1000),
            textEvent("researcher", "second", timestampMs = 2000)
        )
        val received = mutableListOf<Pair<String, String>>()
        poller.onTextMessage = { agent, content -> received.add(agent to content) }

        poller.pollOnce()

        assertThat(received).containsExactly(
            "lead" to "first",
            "researcher" to "second"
        ).inOrder()
    }

    // ---- BitmapPayload: cached via EventProcessor ----

    @Test
    fun bitmapPayload_storedInCacheViaProcessor() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setBitmapPayload(
                    BitmapPayload.newBuilder()
                        .setCacheKey("0xABC")
                        .setImageData(ByteString.copyFrom(pngData))
                )
                .build()
        )

        poller.pollOnce()

        assertThat(cache.contains("0xABC")).isTrue()
        assertThat(cache.get("0xABC")).isEqualTo(pngData)
    }

    // ---- Helpers ----

    private fun textEvent(agentId: String, content: String, timestampMs: Long): Event =
        Event.newBuilder()
            .setTimestampMs(timestampMs)
            .setTextMessage(
                TextMessage.newBuilder()
                    .setAgentId(agentId)
                    .setContent(content)
            )
            .build()

    private fun displayEvent(cacheKey: String, timestampMs: Long): Event =
        Event.newBuilder()
            .setTimestampMs(timestampMs)
            .setDisplayCommand(
                DisplayCommand.newBuilder().setCacheKey(cacheKey)
            )
            .build()

    private fun makeTextEvents(count: Int): List<Event> =
        (1..count).map { i ->
            textEvent("agent", "msg$i", timestampMs = i * 1000L)
        }

    /**
     * Fake SyncService that supports configurable responses and failures.
     */
    private class FakeSyncService : SyncServiceGrpc.SyncServiceImplBase() {
        var eventsToReturn: List<Event> = emptyList()
        var bitmapToReturn: BitmapPayload = BitmapPayload.getDefaultInstance()
        var failNextGetEvents: Boolean = false
        var failNextGetBitmap: Boolean = false
        var lastGetEventsRequest: GetEventsRequest? = null

        override fun getEvents(
            request: GetEventsRequest,
            responseObserver: StreamObserver<GetEventsResponse>
        ) {
            lastGetEventsRequest = request
            if (failNextGetEvents) {
                failNextGetEvents = false
                responseObserver.onError(Status.UNAVAILABLE.asRuntimeException())
                return
            }
            responseObserver.onNext(
                GetEventsResponse.newBuilder().addAllEvents(eventsToReturn).build()
            )
            responseObserver.onCompleted()
        }

        override fun sendUserInput(
            request: SendUserInputRequest,
            responseObserver: StreamObserver<SendUserInputResponse>
        ) {
            responseObserver.onNext(
                SendUserInputResponse.newBuilder().setAccepted(true).build()
            )
            responseObserver.onCompleted()
        }

        override fun getBitmap(
            request: GetBitmapRequest,
            responseObserver: StreamObserver<GetBitmapResponse>
        ) {
            if (failNextGetBitmap) {
                failNextGetBitmap = false
                responseObserver.onError(Status.NOT_FOUND.asRuntimeException())
                return
            }
            responseObserver.onNext(
                GetBitmapResponse.newBuilder().setBitmap(bitmapToReturn).build()
            )
            responseObserver.onCompleted()
        }
    }
}
