package com.vanpilot.auto.grpc

/**
 * Configuration for the supervisor gRPC endpoint.
 *
 * Defaults to localhost:50051 for local development. In production,
 * the host is a Tailscale address (e.g., "macstudio.tailnet") set at
 * runtime via [VanPilotCarAppService].
 */
data class GrpcEndpointConfig(
    val host: String = DEFAULT_HOST,
    val port: Int = DEFAULT_PORT,
) {
    fun toTarget(): String = "$host:$port"

    companion object {
        const val DEFAULT_HOST = "localhost"
        const val DEFAULT_PORT = 50051
    }
}
