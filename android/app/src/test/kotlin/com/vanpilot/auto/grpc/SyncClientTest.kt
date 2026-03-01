package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.BitmapCache
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetBitmapResponse
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.TextMessage
import com.vanpilot.proto.v1.DisplayCommand
import com.vanpilot.proto.v1.BitmapPayload
import io.grpc.ManagedChannel
import io.grpc.Server
import io.grpc.inprocess.InProcessChannelBuilder
import io.grpc.inprocess.InProcessServerBuilder
import io.grpc.stub.StreamObserver
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Fake SyncService implementation for testing SyncClient behavior.
 * Returns controlled responses to exercise adaptive batching and event handling.
 */
class FakeSyncService : SyncServiceGrpc.SyncServiceImplBase() {

    var eventsToReturn: List<Event> = emptyList()
    var shouldFail: Boolean = false
    var lastGetEventsRequest: GetEventsRequest? = null
    var getBitmapResponse: GetBitmapResponse? = null
    var lastGetBitmapCacheKey: String? = null

    override fun getEvents(
        request: GetEventsRequest,
        responseObserver: StreamObserver<GetEventsResponse>,
    ) {
        lastGetEventsRequest = request
        if (shouldFail) {
            responseObserver.onError(
                io.grpc.Status.UNAVAILABLE
                    .withDescription("fake error")
                    .asRuntimeException()
            )
            return
        }
        val response = GetEventsResponse.newBuilder()
            .addAllEvents(eventsToReturn)
            .build()
        responseObserver.onNext(response)
        responseObserver.onCompleted()
    }

    override fun getBitmap(
        request: GetBitmapRequest,
        responseObserver: StreamObserver<GetBitmapResponse>,
    ) {
        lastGetBitmapCacheKey = request.cacheKey
        val resp = getBitmapResponse ?: GetBitmapResponse.getDefaultInstance()
        responseObserver.onNext(resp)
        responseObserver.onCompleted()
    }
}

/**
 * Behavioral tests for SyncClient using an in-process gRPC server.
 *
 * Tests adaptive batching (max_count adjustment on success/error),
 * event dispatching (TextMessage, DisplayCommand), and sync state.
 */
@RunWith(JUnit4::class)
class SyncClientTest {

    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var fakeService: FakeSyncService
    private lateinit var bitmapCache: BitmapCache
    private lateinit var client: SyncClient

    private val displayedKeys = mutableListOf<String>()
    private val textMessages = mutableListOf<Pair<String, String>>()

    @Before
    fun setUp() {
        val serverName = InProcessServerBuilder.generateName()
        fakeService = FakeSyncService()
        server = InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(fakeService)
            .build()
            .start()
        channel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .build()
        bitmapCache = BitmapCache()
        displayedKeys.clear()
        textMessages.clear()
        client = SyncClient(
            channel = channel,
            bitmapCache = bitmapCache,
            onDisplayCommand = { key -> displayedKeys.add(key) },
            onTextMessage = { agentId, content -> textMessages.add(Pair(agentId, content)) },
        )
    }

    @After
    fun tearDown() {
        channel.shutdownNow()
        server.shutdownNow()
    }

    // -----------------------------------------------------------------------
    // Constant verification
    // -----------------------------------------------------------------------

    @Test
    fun defaultMaxCount() {
        assertThat(SyncClient.DEFAULT_MAX_COUNT).isEqualTo(50)
    }

    @Test
    fun reconnectMaxCount() {
        assertThat(SyncClient.RECONNECT_MAX_COUNT).isEqualTo(5)
    }

    @Test
    fun maxBatchSize() {
        assertThat(SyncClient.MAX_BATCH_SIZE).isEqualTo(200)
    }

    // -----------------------------------------------------------------------
    // Adaptive batching
    // -----------------------------------------------------------------------

    @Test
    fun pollEvents_initialMaxCountIsDefault() {
        assertThat(client.maxCount).isEqualTo(SyncClient.DEFAULT_MAX_COUNT)
    }

    @Test
    fun pollEvents_noGrowthOnEmptyResponse() {
        fakeService.eventsToReturn = emptyList()
        client.pollEvents()
        assertThat(client.maxCount).isEqualTo(SyncClient.DEFAULT_MAX_COUNT)
    }

    @Test
    fun pollEvents_doublesMaxCountOnSuccess() {
        fakeService.eventsToReturn = listOf(makeTextEvent(1000L, "agent1", "hello"))
        val initialMax = client.maxCount
        client.pollEvents()
        assertThat(client.maxCount).isEqualTo((initialMax * 2).coerceAtMost(SyncClient.MAX_BATCH_SIZE))
    }

    @Test
    fun pollEvents_maxCountCappedAtMaxBatchSize() {
        // Poll with events repeatedly to grow maxCount
        fakeService.eventsToReturn = listOf(makeTextEvent(1000L, "agent1", "hello"))
        repeat(20) {
            // Update timestamp so events keep coming
            fakeService.eventsToReturn = listOf(
                makeTextEvent(1000L + it.toLong() * 100, "agent1", "msg$it")
            )
            client.pollEvents()
        }
        assertThat(client.maxCount).isAtMost(SyncClient.MAX_BATCH_SIZE)
    }

    @Test
    fun pollEvents_shrinksMaxCountOnError() {
        // First grow it beyond RECONNECT_MAX_COUNT
        fakeService.eventsToReturn = listOf(makeTextEvent(1000L, "agent1", "hello"))
        client.pollEvents()
        assertThat(client.maxCount).isGreaterThan(SyncClient.RECONNECT_MAX_COUNT)

        // Now trigger an error
        fakeService.shouldFail = true
        client.pollEvents()
        assertThat(client.maxCount).isEqualTo(SyncClient.RECONNECT_MAX_COUNT)
    }

    @Test
    fun pollEvents_returnsEmptyListOnError() {
        fakeService.shouldFail = true
        val events = client.pollEvents()
        assertThat(events).isEmpty()
    }

    // -----------------------------------------------------------------------
    // Sync state (sinceTimestampMs)
    // -----------------------------------------------------------------------

    @Test
    fun pollEvents_initialSinceTimestampIsZero() {
        assertThat(client.sinceTimestampMs).isEqualTo(0)
    }

    @Test
    fun pollEvents_advancesSinceTimestamp() {
        fakeService.eventsToReturn = listOf(
            makeTextEvent(1000L, "agent1", "first"),
            makeTextEvent(2000L, "agent1", "second"),
        )
        client.pollEvents()
        // sinceTimestampMs should be last event's timestamp + 1
        assertThat(client.sinceTimestampMs).isEqualTo(2001L)
    }

    @Test
    fun pollEvents_doesNotAdvanceOnEmpty() {
        fakeService.eventsToReturn = emptyList()
        client.pollEvents()
        assertThat(client.sinceTimestampMs).isEqualTo(0)
    }

    @Test
    fun pollEvents_doesNotAdvanceOnError() {
        fakeService.shouldFail = true
        client.pollEvents()
        assertThat(client.sinceTimestampMs).isEqualTo(0)
    }

    @Test
    fun pollEvents_passesCorrectSinceTimestamp() {
        fakeService.eventsToReturn = listOf(makeTextEvent(5000L, "agent1", "hello"))
        client.pollEvents()

        // Next poll should use updated timestamp
        fakeService.eventsToReturn = emptyList()
        client.pollEvents()
        assertThat(fakeService.lastGetEventsRequest?.sinceTimestampMs).isEqualTo(5001L)
    }

    // -----------------------------------------------------------------------
    // resetSync
    // -----------------------------------------------------------------------

    @Test
    fun resetSync_resetsTimestampAndMaxCount() {
        // Advance state
        fakeService.eventsToReturn = listOf(makeTextEvent(5000L, "agent1", "hello"))
        client.pollEvents()
        assertThat(client.sinceTimestampMs).isGreaterThan(0)
        assertThat(client.maxCount).isGreaterThan(SyncClient.RECONNECT_MAX_COUNT)

        client.resetSync()

        assertThat(client.sinceTimestampMs).isEqualTo(0)
        assertThat(client.maxCount).isEqualTo(SyncClient.RECONNECT_MAX_COUNT)
    }

    // -----------------------------------------------------------------------
    // Event handling: TextMessage
    // -----------------------------------------------------------------------

    @Test
    fun pollEvents_dispatchesTextMessage() {
        fakeService.eventsToReturn = listOf(
            makeTextEvent(1000L, "lead", "Hello from lead"),
        )
        client.pollEvents()
        assertThat(textMessages).hasSize(1)
        assertThat(textMessages[0].first).isEqualTo("lead")
        assertThat(textMessages[0].second).isEqualTo("Hello from lead")
    }

    @Test
    fun pollEvents_dispatchesMultipleTextMessages() {
        fakeService.eventsToReturn = listOf(
            makeTextEvent(1000L, "lead", "msg1"),
            makeTextEvent(2000L, "renderer", "msg2"),
        )
        client.pollEvents()
        assertThat(textMessages).hasSize(2)
        assertThat(textMessages[0].first).isEqualTo("lead")
        assertThat(textMessages[1].first).isEqualTo("renderer")
    }

    // -----------------------------------------------------------------------
    // Event handling: DisplayCommand
    // -----------------------------------------------------------------------

    @Test
    fun pollEvents_displayCommandWhenBitmapCached() {
        // Pre-populate cache with a dummy bitmap
        val bitmap = android.graphics.Bitmap.createBitmap(1, 1, android.graphics.Bitmap.Config.ARGB_8888)
        bitmapCache.put("0xCAFE", bitmap)

        fakeService.eventsToReturn = listOf(makeDisplayEvent(1000L, "0xCAFE"))
        client.pollEvents()

        assertThat(displayedKeys).containsExactly("0xCAFE")
    }

    @Test
    fun pollEvents_displayCommandFallsBackToGetBitmap() {
        // Bitmap not in cache, GetBitmap returns empty → display should NOT fire
        fakeService.eventsToReturn = listOf(makeDisplayEvent(1000L, "0xMISSING"))
        fakeService.getBitmapResponse = null  // empty response

        client.pollEvents()

        // GetBitmap was called
        assertThat(fakeService.lastGetBitmapCacheKey).isEqualTo("0xMISSING")
        // Display callback should not fire (bitmap unavailable)
        assertThat(displayedKeys).isEmpty()
    }

    // -----------------------------------------------------------------------
    // BitmapCache
    // -----------------------------------------------------------------------

    @Test
    fun bitmapCacheStartsEmpty() {
        val cache = BitmapCache()
        assertThat(cache.size).isEqualTo(0)
    }

    @Test
    fun bitmapCachePutAndGet() {
        val cache = BitmapCache()
        val bitmap = android.graphics.Bitmap.createBitmap(2, 2, android.graphics.Bitmap.Config.ARGB_8888)
        cache.put("0xABCD", bitmap)
        assertThat(cache.has("0xABCD")).isTrue()
        assertThat(cache.get("0xABCD")).isSameInstanceAs(bitmap)
        assertThat(cache.size).isEqualTo(1)
    }

    @Test
    fun bitmapCacheRemove() {
        val cache = BitmapCache()
        val bitmap = android.graphics.Bitmap.createBitmap(1, 1, android.graphics.Bitmap.Config.ARGB_8888)
        cache.put("0x1234", bitmap)
        cache.remove("0x1234")
        assertThat(cache.has("0x1234")).isFalse()
        assertThat(cache.size).isEqualTo(0)
    }

    @Test
    fun bitmapCacheClear() {
        val cache = BitmapCache()
        val bitmap = android.graphics.Bitmap.createBitmap(1, 1, android.graphics.Bitmap.Config.ARGB_8888)
        cache.put("0xA", bitmap)
        cache.put("0xB", bitmap)
        cache.clear()
        assertThat(cache.size).isEqualTo(0)
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private fun makeTextEvent(timestampMs: Long, agentId: String, content: String): Event {
        return Event.newBuilder()
            .setTimestampMs(timestampMs)
            .setTextMessage(
                TextMessage.newBuilder()
                    .setAgentId(agentId)
                    .setContent(content)
                    .build()
            )
            .build()
    }

    private fun makeDisplayEvent(timestampMs: Long, cacheKey: String): Event {
        return Event.newBuilder()
            .setTimestampMs(timestampMs)
            .setDisplayCommand(
                DisplayCommand.newBuilder()
                    .setCacheKey(cacheKey)
                    .build()
            )
            .build()
    }
}
