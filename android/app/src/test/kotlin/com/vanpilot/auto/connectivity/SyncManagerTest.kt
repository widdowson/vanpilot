package com.vanpilot.auto.connectivity

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.sync.EventProcessor
import com.vanpilot.proto.v1.BitmapPayload
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetBitmapResponse
import com.vanpilot.proto.v1.SendUserInputRequest
import com.vanpilot.proto.v1.SendUserInputResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.TextMessage
import io.grpc.ManagedChannel
import io.grpc.Server
import io.grpc.Status
import io.grpc.StatusRuntimeException
import io.grpc.inprocess.InProcessChannelBuilder
import io.grpc.inprocess.InProcessServerBuilder
import io.grpc.stub.StreamObserver
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for SyncManager - orchestrates polling with connection awareness.
 *
 * AC-9.1: Detects loss of connectivity.
 * AC-9.4: On reconnection, sync resumes from the last known timestamp.
 * AC-9.5: Adaptive batching starts conservatively on reconnection.
 */
@RunWith(JUnit4::class)
class SyncManagerTest {

    private lateinit var serverName: String
    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var fakeService: FakeSyncService
    private lateinit var syncManager: SyncManager
    private lateinit var bitmapCache: BitmapCache
    private lateinit var eventProcessor: EventProcessor

    @Before
    fun setUp() {
        serverName = InProcessServerBuilder.generateName()
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
        eventProcessor = EventProcessor(bitmapCache)
        syncManager = SyncManager(channel, eventProcessor)
    }

    @After
    fun tearDown() {
        syncManager.shutdown()
        server.shutdownNow()
    }

    // --- AC-9.1: Connection state detection ---

    @Test
    fun initialConnectionState_isDisconnected() {
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun afterSuccessfulPoll_stateIsConnected() {
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.CONNECTED)
    }

    @Test
    fun afterFailedPoll_stateIsDisconnected() {
        fakeService.shouldFail = true
        syncManager.poll()
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun afterReconnectionPoll_stateIsConnected() {
        // Connect
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.CONNECTED)

        // Disconnect
        fakeService.shouldFail = true
        syncManager.poll()
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.DISCONNECTED)

        // Reconnect
        fakeService.shouldFail = false
        syncManager.poll()
        assertThat(syncManager.connectionState).isEqualTo(ConnectionState.CONNECTED)
    }

    // --- AC-9.4: Sync resumes from last known timestamp ---

    @Test
    fun poll_usesTimestampFromLastEvent() {
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("a"))
                .build(),
            Event.newBuilder()
                .setTimestampMs(2000)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("b"))
                .build()
        )

        syncManager.poll()

        // Next poll should use timestamp of last event
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()

        assertThat(fakeService.lastGetEventsRequest?.sinceTimestampMs).isEqualTo(2000)
    }

    @Test
    fun afterDisconnectAndReconnect_resumesFromLastTimestamp() {
        // First successful poll with events
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(5000)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("hello"))
                .build()
        )
        syncManager.poll()

        // Disconnect
        fakeService.shouldFail = true
        syncManager.poll()

        // Reconnect
        fakeService.shouldFail = false
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()

        // Should resume from last known timestamp (5000), not reset to 0
        assertThat(fakeService.lastGetEventsRequest?.sinceTimestampMs).isEqualTo(5000)
    }

    @Test
    fun poll_processesEventsViaEventProcessor() {
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setTextMessage(TextMessage.newBuilder().setAgentId("lead").setContent("hello"))
                .build()
        )

        syncManager.poll()

        assertThat(eventProcessor.textMessages).hasSize(1)
        assertThat(eventProcessor.textMessages[0].content).isEqualTo("hello")
    }

    // --- AC-9.5: Adaptive batching ---

    @Test
    fun initialPoll_usesStableMaxCount() {
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()

        assertThat(fakeService.lastGetEventsRequest?.maxCount).isEqualTo(50)
    }

    @Test
    fun afterReconnection_usesConservativeMaxCount() {
        // Connect
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()

        // Disconnect
        fakeService.shouldFail = true
        syncManager.poll()

        // Reconnect - should use conservative batch size
        fakeService.shouldFail = false
        syncManager.poll()

        assertThat(fakeService.lastGetEventsRequest?.maxCount).isEqualTo(5)
    }

    @Test
    fun afterMultipleSuccessfulPollsPostReconnection_maxCountIncreases() {
        // Connect then disconnect
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()
        fakeService.shouldFail = true
        syncManager.poll()

        // Reconnect
        fakeService.shouldFail = false
        syncManager.poll()
        val initialMaxCount = fakeService.lastGetEventsRequest?.maxCount ?: 0

        // Multiple successful polls
        repeat(10) { syncManager.poll() }

        val laterMaxCount = fakeService.lastGetEventsRequest?.maxCount ?: 0
        assertThat(laterMaxCount).isGreaterThan(initialMaxCount)
    }

    @Test
    fun afterFailure_maxCountDropsToConservative() {
        fakeService.eventsToReturn = emptyList()
        syncManager.poll()

        fakeService.shouldFail = true
        syncManager.poll()

        fakeService.shouldFail = false
        syncManager.poll()

        // After a failure/reconnect cycle, max_count should be conservative
        assertThat(fakeService.lastGetEventsRequest?.maxCount).isEqualTo(5)
    }

    // --- AC-9.2: Last bitmap retained ---

    @Test
    fun afterDisconnect_eventProcessorRetainsState() {
        // Process a display command
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setBitmapPayload(
                    BitmapPayload.newBuilder()
                        .setCacheKey("0xCAFE")
                        .setImageData(ByteString.copyFrom(byteArrayOf(1, 2, 3)))
                )
                .build()
        )
        syncManager.poll()

        // Disconnect
        fakeService.shouldFail = true
        syncManager.poll()

        // Bitmap cache should still have the bitmap
        assertThat(bitmapCache.contains("0xCAFE")).isTrue()
    }

    // --- Connection state listener ---

    @Test
    fun connectionStateListener_notifiedOnChanges() {
        val states = mutableListOf<ConnectionState>()
        syncManager.addConnectionListener { states.add(it) }

        fakeService.eventsToReturn = emptyList()
        syncManager.poll() // CONNECTED

        fakeService.shouldFail = true
        syncManager.poll() // DISCONNECTED

        assertThat(states).containsExactly(
            ConnectionState.CONNECTED,
            ConnectionState.DISCONNECTED
        ).inOrder()
    }

    /**
     * Fake SyncService that can simulate failures.
     */
    private class FakeSyncService : SyncServiceGrpc.SyncServiceImplBase() {
        var eventsToReturn: List<Event> = emptyList()
        var shouldFail: Boolean = false
        var lastGetEventsRequest: GetEventsRequest? = null

        override fun getEvents(
            request: GetEventsRequest,
            responseObserver: StreamObserver<GetEventsResponse>
        ) {
            lastGetEventsRequest = request
            if (shouldFail) {
                responseObserver.onError(
                    StatusRuntimeException(Status.UNAVAILABLE.withDescription("Connection lost"))
                )
                return
            }
            val response = GetEventsResponse.newBuilder()
                .addAllEvents(eventsToReturn)
                .build()
            responseObserver.onNext(response)
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
            responseObserver.onNext(GetBitmapResponse.getDefaultInstance())
            responseObserver.onCompleted()
        }
    }
}
