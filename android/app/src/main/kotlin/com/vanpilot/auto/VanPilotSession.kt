package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.Screen
import androidx.car.app.Session

/**
 * Represents a single connection session between the Android Auto host
 * and the VanPilot app. Returns the main screen on creation.
 */
class VanPilotSession : Session() {

    override fun onCreateScreen(intent: Intent): Screen {
        return VanPilotScreen(carContext)
    }
}
