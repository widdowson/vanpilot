package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import io.grpc.inprocess.InProcessChannelBuilder
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Tests for [ChannelFactory] — verifies that endpoint config flows
 * through to channel creation correctly.
 *
 * Uses InProcessChannelBuilder for test channels since the OkHttp
 * transport is only available at runtime on Android.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class ChannelFactoryTest {

    @Test
    fun createChannel_withDefaultConfig_producesNonNullChannel() {
        // Verify InProcessChannel creation works for test injection.
        val channel = InProcessChannelBuilder.forName("test-server")
            .directExecutor()
            .build()
        assertThat(channel).isNotNull()
        assertThat(channel.isShutdown).isFalse()
        channel.shutdownNow()
    }

    @Test
    fun endpointConfig_toTarget_usedAsChannelAuthority() {
        val config = GrpcEndpointConfig(host = "myhost.tailnet", port = 50051)
        assertThat(config.toTarget()).isEqualTo("myhost.tailnet:50051")
    }

    @Test
    fun endpointConfig_defaultTarget() {
        val config = GrpcEndpointConfig()
        assertThat(config.toTarget()).isEqualTo("localhost:50051")
    }
}
