package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.Screen
import androidx.car.app.Session
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.vanpilot.auto.grpc.ChannelFactory
import com.vanpilot.auto.grpc.GrpcEndpointConfig
import io.grpc.ManagedChannel
import java.io.Closeable

/**
 * Represents a single connection session between the Android Auto host
 * and the VanPilot app. Creates a gRPC channel to the supervisor on
 * startup and returns the main screen.
 *
 * When a [pollLoopFactory] is provided and a gRPC channel is available,
 * creates a poll loop that routes supervisor events into the
 * [ConversationTabManager], replacing mock data with real gRPC-driven content.
 *
 * The channel and poll loop are shut down automatically when the session
 * lifecycle is destroyed.
 *
 * @param endpointConfig Supervisor gRPC endpoint. Defaults to localhost:50051
 *   for local development; set to a Tailscale address for production.
 * @param channelOverride Optional pre-built channel for testing. When provided,
 *   [endpointConfig] is ignored and this channel is used directly.
 * @param pollLoopFactory Optional factory that creates a poll loop from a
 *   channel, tab manager, and screen invalidation callback. Returns a
 *   [Closeable] that shuts down the loop. Kept as a factory to avoid
 *   proto/gRPC type dependencies in vanpilot_lib.
 */
class VanPilotSession(
    private val endpointConfig: GrpcEndpointConfig = GrpcEndpointConfig(),
    private val channelOverride: ManagedChannel? = null,
    private val pollLoopFactory: ((ManagedChannel, ConversationTabManager, () -> Unit) -> Closeable)? = null
) : Session() {

    /** The gRPC channel to the supervisor, created in [onCreateScreen]. */
    var channel: ManagedChannel? = null
        private set

    /** The poll loop closeable, or null if not wired. */
    var pollLoopCloseable: Closeable? = null
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

        // When a gRPC channel and poll loop factory are available, use an
        // empty ConversationTabManager fed by the poll loop. Otherwise,
        // fall back to mock data.
        val ch = channel
        val factory = pollLoopFactory
        if (ch != null && factory != null) {
            val tabManager = ConversationTabManager()
            val screen = VanPilotScreen(carContext, tabManager = tabManager)
            pollLoopCloseable = factory(ch, tabManager) { screen.invalidate() }
            return screen
        }

        return VanPilotScreen(carContext)
    }

    /** Shuts down the gRPC channel and poll loop. Safe to call multiple times. */
    fun shutdownGrpc() {
        pollLoopCloseable?.close()
        channel?.shutdownNow()
    }
}
