package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.Screen
import androidx.car.app.Session
import com.vanpilot.auto.grpc.ChannelFactory
import com.vanpilot.auto.grpc.GrpcEndpointConfig
import io.grpc.ManagedChannel

/**
 * Represents a single connection session between the Android Auto host
 * and the VanPilot app. Creates a gRPC channel to the supervisor on
 * startup and returns the main screen.
 *
 * @param endpointConfig Supervisor gRPC endpoint. Defaults to localhost:50051
 *   for local development; set to a Tailscale address for production.
 * @param channelOverride Optional pre-built channel for testing. When provided,
 *   [endpointConfig] is ignored and this channel is used directly.
 */
class VanPilotSession(
    private val endpointConfig: GrpcEndpointConfig = GrpcEndpointConfig(),
    private val channelOverride: ManagedChannel? = null
) : Session() {

    /** The gRPC channel to the supervisor, created in [onCreateScreen]. */
    var channel: ManagedChannel? = null
        private set

    override fun onCreateScreen(intent: Intent): Screen {
        // Use injected channel for tests, or create one from endpoint config.
        // Tailscale provides the encrypted tunnel, so plaintext is safe here.
        channel = channelOverride ?: ChannelFactory.createChannel(endpointConfig)
        return VanPilotScreen(carContext)
    }

    /** Shuts down the gRPC channel. Called when the session is destroyed. */
    fun shutdownGrpc() {
        channel?.shutdownNow()
    }
}
