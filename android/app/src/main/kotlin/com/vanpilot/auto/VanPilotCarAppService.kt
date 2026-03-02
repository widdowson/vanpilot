package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.CarAppService
import androidx.car.app.Session
import androidx.car.app.validation.HostValidator
import com.vanpilot.auto.grpc.GrpcEndpointConfig

/**
 * Entry point for the VanPilot Android Auto app.
 * Declares itself as a navigation-category app to gain access to
 * NavigationTemplate's SurfaceCallback for custom rendering.
 */
class VanPilotCarAppService : CarAppService() {

    companion object {
        /**
         * Supervisor gRPC endpoint configuration.
         *
         * Defaults to localhost:50051 for local development. For production
         * with Tailscale, set this before the service starts (e.g., from
         * Application.onCreate or a settings screen):
         *
         *   VanPilotCarAppService.endpointConfig =
         *       GrpcEndpointConfig(host = "macstudio.tailnet", port = 50051)
         */
        var endpointConfig = GrpcEndpointConfig()
    }

    override fun createHostValidator(): HostValidator {
        // Allow all hosts since VanPilot is sideloaded, not distributed via Play Store.
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR
    }

    override fun onCreateSession(): Session {
        return VanPilotSession(endpointConfig)
    }
}
