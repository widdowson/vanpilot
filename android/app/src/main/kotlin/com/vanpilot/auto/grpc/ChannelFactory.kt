package com.vanpilot.auto.grpc

import io.grpc.ManagedChannel
import io.grpc.ManagedChannelBuilder

/**
 * Creates gRPC [ManagedChannel] instances from endpoint configuration.
 *
 * Uses plaintext (no TLS) because the Tailscale tunnel provides
 * encryption at the network layer. The actual channel transport
 * (OkHttp on Android) is resolved at runtime via SPI.
 */
object ChannelFactory {

    /**
     * Creates a [ManagedChannel] pointing at the given endpoint.
     *
     * At runtime on Android, this resolves to an OkHttp-backed channel
     * because grpc-okhttp is on the classpath. For tests, inject a
     * channel built with [io.grpc.inprocess.InProcessChannelBuilder].
     */
    fun createChannel(config: GrpcEndpointConfig): ManagedChannel {
        @Suppress("DEPRECATION") // forTarget is the correct API for our use case
        return ManagedChannelBuilder
            .forTarget(config.toTarget())
            .usePlaintext()
            .build()
    }
}
