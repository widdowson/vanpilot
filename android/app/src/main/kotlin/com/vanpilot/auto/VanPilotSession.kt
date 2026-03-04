package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.Screen
import androidx.car.app.Session
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.vanpilot.auto.grpc.ChannelFactory
import com.vanpilot.auto.grpc.GrpcEndpointConfig
import io.grpc.ManagedChannel

/**
 * Represents a single connection session between the Android Auto host
 * and the VanPilot app. Creates a gRPC channel to the supervisor on
 * startup and returns the main screen.
 *
 * The channel is shut down automatically when the session lifecycle is
 * destroyed, preventing ManagedChannel leaks.
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
        // Channel creation may fail if grpc-okhttp is not on the classpath
        // (e.g., during DHU testing without a supervisor). The app still
        // renders its default teal surface in that case.
        channel = channelOverride ?: try {
            ChannelFactory.createChannel(endpointConfig)
        } catch (_: Exception) {
            null
        }

        // Shut down the channel when the session is destroyed.
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onDestroy(owner: LifecycleOwner) {
                shutdownGrpc()
            }
        })

        return VanPilotScreen(carContext)
    }

    /** Shuts down the gRPC channel. Safe to call multiple times. */
    fun shutdownGrpc() {
        channel?.shutdownNow()
    }
}
