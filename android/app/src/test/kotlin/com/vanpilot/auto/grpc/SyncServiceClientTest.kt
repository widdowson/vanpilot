package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.ByteString
import com.vanpilot.proto.v1.BitmapPayload
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetBitmapResponse
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.GetEventsResponse
import com.vanpilot.proto.v1.SendUserInputRequest
import com.vanpilot.proto.v1.SendUserInputResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.TextMessage
import io.grpc.ManagedChannel
import io.grpc.inprocess.InProcessChannelBuilder
import io.grpc.inprocess.InProcessServerBuilder
import io.grpc.stub.StreamObserver
import io.grpc.Server
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class SyncServiceClientTest {

    private lateinit var serverName: String
    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var client: SyncServiceClient

    private val fakeService = FakeSyncService()

    @Before
    fun setUp() {
        serverName = InProcessServerBuilder.generateName()
        server = InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(fakeService)
            .build()
            .start()
        channel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .build()
        client = SyncServiceClient(channel)
    }

    @After
    fun tearDown() {
        client.shutdown()
        server.shutdownNow()
    }

    @Test
    fun getEvents_returnsEventsFromServer() {
        fakeService.eventsToReturn = listOf(
            Event.newBuilder()
                .setTimestampMs(1000)
                .setTextMessage(
                    TextMessage.newBuilder()
                        .setAgentId("lead")
                        .setContent("Hello")
                )
                .build(),
            Event.newBuilder()
                .setTimestampMs(2000)
                .setTextMessage(
                    TextMessage.newBuilder()
                        .setAgentId("lead")
                        .setContent("World")
                )
                .build()
        )

        val response = client.getEvents(sinceTimestampMs = 0, maxCount = 10)

        assertThat(response.eventsList).hasSize(2)
        assertThat(response.eventsList[0].textMessage.content).isEqualTo("Hello")
        assertThat(response.eventsList[1].textMessage.content).isEqualTo("World")
    }

    @Test
    fun getEvents_passesSinceTimestampAndMaxCount() {
        client.getEvents(sinceTimestampMs = 5000, maxCount = 3)

        assertThat(fakeService.lastGetEventsRequest?.sinceTimestampMs).isEqualTo(5000)
        assertThat(fakeService.lastGetEventsRequest?.maxCount).isEqualTo(3)
    }

    @Test
    fun getEvents_emptyResponse() {
        fakeService.eventsToReturn = emptyList()

        val response = client.getEvents(sinceTimestampMs = 0, maxCount = 10)

        assertThat(response.eventsList).isEmpty()
    }

    @Test
    fun sendUserInput_returnsAccepted() {
        fakeService.acceptInput = true

        val response = client.sendUserInput(text = "deploy the app", targetAgentId = "lead")

        assertThat(response.accepted).isTrue()
    }

    @Test
    fun sendUserInput_passesTextAndTargetAgent() {
        client.sendUserInput(text = "run tests", targetAgentId = "researcher")

        assertThat(fakeService.lastSendUserInputRequest?.text).isEqualTo("run tests")
        assertThat(fakeService.lastSendUserInputRequest?.targetAgentId).isEqualTo("researcher")
    }

    @Test
    fun sendUserInput_defaultTargetAgent() {
        client.sendUserInput(text = "hello")

        assertThat(fakeService.lastSendUserInputRequest?.targetAgentId).isEqualTo("lead")
    }

    @Test
    fun getBitmap_returnsBitmapPayload() {
        val pngData = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        fakeService.bitmapToReturn = BitmapPayload.newBuilder()
            .setCacheKey("0xCAFE")
            .setImageData(ByteString.copyFrom(pngData))
            .setWidthPx(800)
            .setHeightPx(480)
            .build()

        val response = client.getBitmap(cacheKey = "0xCAFE")

        assertThat(response.bitmap.cacheKey).isEqualTo("0xCAFE")
        assertThat(response.bitmap.imageData.toByteArray()).isEqualTo(pngData)
        assertThat(response.bitmap.widthPx).isEqualTo(800)
        assertThat(response.bitmap.heightPx).isEqualTo(480)
    }

    @Test
    fun getBitmap_passesCacheKey() {
        client.getBitmap(cacheKey = "0xDEAD")

        assertThat(fakeService.lastGetBitmapRequest?.cacheKey).isEqualTo("0xDEAD")
    }

    /**
     * Fake SyncService implementation for testing the client.
     */
    private class FakeSyncService : SyncServiceGrpc.SyncServiceImplBase() {
        var eventsToReturn: List<Event> = emptyList()
        var acceptInput: Boolean = true
        var bitmapToReturn: BitmapPayload = BitmapPayload.getDefaultInstance()

        var lastGetEventsRequest: GetEventsRequest? = null
        var lastSendUserInputRequest: SendUserInputRequest? = null
        var lastGetBitmapRequest: GetBitmapRequest? = null

        override fun getEvents(
            request: GetEventsRequest,
            responseObserver: StreamObserver<GetEventsResponse>
        ) {
            lastGetEventsRequest = request
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
            lastSendUserInputRequest = request
            val response = SendUserInputResponse.newBuilder()
                .setAccepted(acceptInput)
                .build()
            responseObserver.onNext(response)
            responseObserver.onCompleted()
        }

        override fun getBitmap(
            request: GetBitmapRequest,
            responseObserver: StreamObserver<GetBitmapResponse>
        ) {
            lastGetBitmapRequest = request
            val response = GetBitmapResponse.newBuilder()
                .setBitmap(bitmapToReturn)
                .build()
            responseObserver.onNext(response)
            responseObserver.onCompleted()
        }
    }
}
