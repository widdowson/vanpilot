package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.vanpilot.proto.v1.ReportThemeRequest
import com.vanpilot.proto.v1.ReportThemeResponse
import com.vanpilot.proto.v1.SyncServiceGrpc
import com.vanpilot.proto.v1.ThemeMode
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

@RunWith(JUnit4::class)
class SyncServiceClientReportThemeTest {

    private lateinit var server: Server
    private lateinit var channel: ManagedChannel
    private lateinit var client: SyncServiceClient

    private var lastReceivedTheme: ThemeMode? = null
    private var respondAcknowledged: Boolean = true

    private val fakeService = object : SyncServiceGrpc.SyncServiceImplBase() {
        override fun reportTheme(
            request: ReportThemeRequest,
            responseObserver: StreamObserver<ReportThemeResponse>
        ) {
            lastReceivedTheme = request.theme
            responseObserver.onNext(
                ReportThemeResponse.newBuilder()
                    .setAcknowledged(respondAcknowledged)
                    .build()
            )
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
    }

    @After
    fun tearDown() {
        client.shutdown()
        server.shutdownNow()
    }

    @Test
    fun reportTheme_dark_sendsCorrectThemeMode() {
        val response = client.reportTheme(ThemeMode.THEME_MODE_DARK)
        assertThat(lastReceivedTheme).isEqualTo(ThemeMode.THEME_MODE_DARK)
        assertThat(response.acknowledged).isTrue()
    }

    @Test
    fun reportTheme_light_sendsCorrectThemeMode() {
        val response = client.reportTheme(ThemeMode.THEME_MODE_LIGHT)
        assertThat(lastReceivedTheme).isEqualTo(ThemeMode.THEME_MODE_LIGHT)
        assertThat(response.acknowledged).isTrue()
    }

    @Test
    fun reportTheme_acknowledged_returnsTrue() {
        respondAcknowledged = true
        val response = client.reportTheme(ThemeMode.THEME_MODE_DARK)
        assertThat(response.acknowledged).isTrue()
    }

    @Test
    fun reportTheme_notAcknowledged_returnsFalse() {
        respondAcknowledged = false
        val response = client.reportTheme(ThemeMode.THEME_MODE_DARK)
        assertThat(response.acknowledged).isFalse()
    }
}
