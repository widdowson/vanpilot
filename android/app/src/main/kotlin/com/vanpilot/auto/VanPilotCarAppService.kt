package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.CarAppService
import androidx.car.app.Session
import androidx.car.app.validation.HostValidator

/**
 * Entry point for the VanPilot Android Auto app.
 * Declares itself as a navigation-category app to gain access to
 * NavigationTemplate's SurfaceCallback for custom rendering.
 */
class VanPilotCarAppService : CarAppService() {

    override fun createHostValidator(): HostValidator {
        // Allow all hosts since VanPilot is sideloaded, not distributed via Play Store.
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR
    }

    override fun onCreateSession(): Session {
        return VanPilotSession()
    }
}
