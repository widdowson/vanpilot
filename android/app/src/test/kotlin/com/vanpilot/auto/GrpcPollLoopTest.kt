package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.connectivity.ConnectionState
import com.vanpilot.auto.sync.EventProcessor
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.TextMessage
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
 * Tests for GrpcPollLoop — the bridge that routes gRPC events
 * from the supervisor into the ConversationTabManager.
 *
 * TDD: These tests were written before the implementation.
 */
@RunWith(JUnit4::class)
class GrpcPollLoopTest {

    private lateinit var serverName: String
    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var fakeService: FakeSyncService
    private lateinit var tabManager: ConversationTabManager
    private lateinit var bitmapCache: BitmapCache
    private lateinit var pollLoop: GrpcPollLoop
    private var updateCount = 0

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
        tabManager = ConversationTabManager()
        bitmapCache = BitmapCache()
        updateCount = 0
        pollLoop = GrpcPollLoop(channel, tabManager, bitmapCache) { updateCount++ }
    }

    @After
    fun tearDown() {
        pollLoop.shutdown()
        server.shutdownNow()
    }

    // --- Lead agent message routing ---

    @Test
    fun poll_leadAgentTextMessage_addedToTabManager() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "Starting analysis...", 1000L)
        )

        pollLoop.poll()

        val messages = tabManager.getLeadAgentMessages()
        assertThat(messages).hasSize(1)
        assertThat(messages[0].text).isEqualTo("Starting analysis...")
        assertThat(messages[0].sender).isEqualTo("lead")
        assertThat(messages[0].timestampMs).isEqualTo(1000L)
    }

    @Test
    fun poll_multipleLeadMessages_allAddedInOrder() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "first", 1000L),
            textEvent("lead", "second", 2000L),
            textEvent("lead", "third", 3000L)
        )

        pollLoop.poll()

        val messages = tabManager.getLeadAgentMessages()
        assertThat(messages).hasSize(3)
        assertThat(messages.map { it.text }).containsExactly("first", "second", "third").inOrder()
    }

    // --- Sub-agent message routing ---

    @Test
    fun poll_subAgentTextMessage_createsSubAgentAndAddsMessage() {
        fakeService.eventsToReturn = listOf(
            textEvent("researcher", "Investigating auth module.", 1500L)
        )

        pollLoop.poll()

        assertThat(tabManager.getSubAgentIds()).containsExactly("researcher")
        val messages = tabManager.getSubAgentMessages("researcher")
        assertThat(messages).hasSize(1)
        assertThat(messages[0].text).isEqualTo("Investigating auth module.")
        assertThat(messages[0].sender).isEqualTo("researcher")
    }

    @Test
    fun poll_multipleSubAgents_eachGetOwnTab() {
        fakeService.eventsToReturn = listOf(
            textEvent("researcher", "msg1", 1000L),
            textEvent("coder", "msg2", 2000L)
        )

        pollLoop.poll()

        assertThat(tabManager.getSubAgentIds()).containsExactly("researcher", "coder").inOrder()
        assertThat(tabManager.getSubAgentMessages("researcher")).hasSize(1)
        assertThat(tabManager.getSubAgentMessages("coder")).hasSize(1)
    }

    @Test
    fun poll_existingSubAgent_doesNotDuplicate() {
        fakeService.eventsToReturn = listOf(
            textEvent("researcher", "msg1", 1000L)
        )
        pollLoop.poll()

        fakeService.eventsToReturn = listOf(
            textEvent("researcher", "msg2", 2000L)
        )
        pollLoop.poll()

        assertThat(tabManager.getSubAgentIds()).containsExactly("researcher")
        assertThat(tabManager.getSubAgentMessages("researcher")).hasSize(2)
    }

    // --- Update callback ---

    @Test
    fun poll_withTextMessages_callsOnUpdate() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "hello", 1000L)
        )

        pollLoop.poll()

        assertThat(updateCount).isGreaterThan(0)
    }

    @Test
    fun poll_withNoEvents_doesNotCallOnUpdate() {
        fakeService.eventsToReturn = emptyList()

        pollLoop.poll()

        assertThat(updateCount).isEqualTo(0)
    }

    // --- Connection state ---

    @Test
    fun connectionState_initiallyDisconnected() {
        assertThat(pollLoop.connectionState).isEqualTo(ConnectionState.DISCONNECTED)
    }

    @Test
    fun connectionState_connectedAfterSuccessfulPoll() {
        fakeService.eventsToReturn = emptyList()
        pollLoop.poll()
        assertThat(pollLoop.connectionState).isEqualTo(ConnectionState.CONNECTED)
    }

    // --- Mixed lead + sub-agent messages ---

    @Test
    fun poll_mixedMessages_routedCorrectly() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "Delegating to researcher", 1000L),
            textEvent("researcher", "On it", 1500L),
            textEvent("lead", "Also delegating to coder", 2000L),
            textEvent("coder", "Starting work", 2500L)
        )

        pollLoop.poll()

        assertThat(tabManager.getLeadAgentMessages()).hasSize(2)
        assertThat(tabManager.getSubAgentIds()).containsExactly("researcher", "coder").inOrder()
        assertThat(tabManager.getSubAgentMessages("researcher")).hasSize(1)
        assertThat(tabManager.getSubAgentMessages("coder")).hasSize(1)
    }

    // --- Incremental polling ---

    @Test
    fun poll_incrementalPolling_accumulatesMessages() {
        fakeService.eventsToReturn = listOf(
            textEvent("lead", "batch1", 1000L)
        )
        pollLoop.poll()

        fakeService.eventsToReturn = listOf(
            textEvent("lead", "batch2", 2000L)
        )
        pollLoop.poll()

        assertThat(tabManager.getLeadAgentMessages()).hasSize(2)
        assertThat(tabManager.getLeadAgentMessages().map { it.text })
            .containsExactly("batch1", "batch2").inOrder()
    }

    // --- Helpers ---

    private fun textEvent(agentId: String, content: String, timestampMs: Long): Event {
        return Event.newBuilder()
            .setTimestampMs(timestampMs)
            .setTextMessage(
                TextMessage.newBuilder()
                    .setAgentId(agentId)
                    .setContent(content)
            )
            .build()
    }

    private class FakeSyncService : SyncServiceGrpc.SyncServiceImplBase() {
        var eventsToReturn: List<Event> = emptyList()

        override fun getEvents(
            request: GetEventsRequest,
            responseObserver: StreamObserver<GetEventsResponse>
        ) {
            val response = GetEventsResponse.newBuilder()
                .addAllEvents(eventsToReturn)
                .build()
            responseObserver.onNext(response)
            responseObserver.onCompleted()
        }
    }
}
