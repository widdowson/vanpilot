package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Tests for [GrpcEndpointConfig] — the supervisor gRPC endpoint configuration.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class GrpcEndpointConfigTest {

    @Test
    fun defaultConfig_usesLocalhostAndPort50051() {
        val config = GrpcEndpointConfig()
        assertThat(config.host).isEqualTo("localhost")
        assertThat(config.port).isEqualTo(50051)
    }

    @Test
    fun toTarget_combinesHostAndPort() {
        val config = GrpcEndpointConfig(host = "pixel.tailnet", port = 9999)
        assertThat(config.toTarget()).isEqualTo("pixel.tailnet:9999")
    }

    @Test
    fun defaultConfig_toTarget() {
        val config = GrpcEndpointConfig()
        assertThat(config.toTarget()).isEqualTo("localhost:50051")
    }

    @Test
    fun customConfig_preservesValues() {
        val config = GrpcEndpointConfig(host = "10.0.0.1", port = 12345)
        assertThat(config.host).isEqualTo("10.0.0.1")
        assertThat(config.port).isEqualTo(12345)
    }
}
