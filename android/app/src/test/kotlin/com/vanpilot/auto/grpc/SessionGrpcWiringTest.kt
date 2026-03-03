package com.vanpilot.auto.grpc

import android.content.Intent
import androidx.car.app.testing.SessionController
import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.VanPilotSession
import io.grpc.inprocess.InProcessChannelBuilder
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Tests that VanPilotSession correctly wires a gRPC channel from endpoint config.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class SessionGrpcWiringTest {

    private lateinit var session: VanPilotSession

    @After
    fun tearDown() {
        if (::session.isInitialized) {
            session.shutdownGrpc()
        }
    }

    @Test
    fun session_withInjectedChannel_usesIt() {
        val channel = InProcessChannelBuilder.forName("test-supervisor")
            .directExecutor()
            .build()
        session = VanPilotSession(channelOverride = channel)
        val testCarContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        SessionController(session, testCarContext, Intent())
        session.onCreateScreen(Intent())

        assertThat(session.channel).isSameInstanceAs(channel)
    }

    @Test
    fun session_withDefaultConfig_storesEndpointConfig() {
        // Verify default config is localhost:50051
        val config = GrpcEndpointConfig()
        assertThat(config.host).isEqualTo("localhost")
        assertThat(config.port).isEqualTo(50051)
        assertThat(config.toTarget()).isEqualTo("localhost:50051")
    }

    @Test
    fun session_withCustomConfig_usesToTarget() {
        val config = GrpcEndpointConfig(host = "macstudio.tailnet", port = 50051)
        assertThat(config.toTarget()).isEqualTo("macstudio.tailnet:50051")
    }

    @Test
    fun session_shutdownGrpc_closesChannel() {
        val channel = InProcessChannelBuilder.forName("test-shutdown")
            .directExecutor()
            .build()
        session = VanPilotSession(channelOverride = channel)
        val testCarContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        SessionController(session, testCarContext, Intent())
        session.onCreateScreen(Intent())

        session.shutdownGrpc()
        assertThat(session.channel!!.isShutdown).isTrue()
    }

    @Test
    fun session_channelIsNullBeforeOnCreateScreen() {
        val channel = InProcessChannelBuilder.forName("test-null-check")
            .directExecutor()
            .build()
        session = VanPilotSession(channelOverride = channel)
        assertThat(session.channel).isNull()
        channel.shutdownNow()
    }
}
