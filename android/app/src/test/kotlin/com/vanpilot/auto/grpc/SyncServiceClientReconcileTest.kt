package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.vanpilot.proto.v1.ReconcileCacheRequest
import com.vanpilot.proto.v1.ReconcileCacheResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
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
 * Tests for SyncServiceClient.reconcileCache (AC-7.4).
 */
@RunWith(JUnit4::class)
class SyncServiceClientReconcileTest {

    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var client: SyncServiceClient
    private val lastReconcileRequest = mutableListOf<ReconcileCacheRequest>()

    private val fakeService = object : SyncServiceGrpc.SyncServiceImplBase() {
        override fun reconcileCache(
            request: ReconcileCacheRequest,
            responseObserver: StreamObserver<ReconcileCacheResponse>
        ) {
            lastReconcileRequest.add(request)
            val response = ReconcileCacheResponse.newBuilder()
                .addMissingKeys("0xMISS1")
                .addMissingKeys("0xMISS2")
                .build()
            responseObserver.onNext(response)
            responseObserver.onCompleted()
        }
    }

    @Before
    fun setUp() {
        val serverName = InProcessServerBuilder.generateName()
        server = InProcessServerBuilder.forName(serverName)
            .directExecutor()
            .addService(fakeService)
            .build()
            .start()
        channel = InProcessChannelBuilder.forName(serverName)
            .directExecutor()
            .build()
        client = SyncServiceClient(channel)
        lastReconcileRequest.clear()
    }

    @After
    fun tearDown() {
        channel.shutdownNow()
        server.shutdownNow()
    }

    @Test
    fun reconcileCache_returnsMissingKeys() {
        val response = client.reconcileCache(listOf("0xA", "0xB"))

        assertThat(response.missingKeysList).containsExactly("0xMISS1", "0xMISS2")
    }

    @Test
    fun reconcileCache_passesPresentKeys() {
        client.reconcileCache(listOf("0xHAVE1", "0xHAVE2"))

        assertThat(lastReconcileRequest).hasSize(1)
        assertThat(lastReconcileRequest[0].presentKeysList)
            .containsExactly("0xHAVE1", "0xHAVE2")
    }

    @Test
    fun reconcileCache_emptyPresent() {
        val response = client.reconcileCache(emptyList())

        assertThat(lastReconcileRequest).hasSize(1)
        assertThat(lastReconcileRequest[0].presentKeysList).isEmpty()
        assertThat(response.missingKeysList).isNotEmpty()
    }
}
