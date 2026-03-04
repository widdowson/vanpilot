package com.vanpilot.auto

import androidx.car.app.AppManager
import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Action
import androidx.car.app.model.ActionStrip
import androidx.car.app.navigation.model.NavigationTemplate

/**
 * The main screen of the VanPilot Android Auto app.
 *
 * Uses NavigationTemplate as the root template to provide a full-screen
 * SurfaceCallback canvas for bitmap rendering. The surface is drawn by
 * [VanPilotSurfaceCallback] which fills the canvas with the brand teal
 * color (light mode) or dark teal (dark mode), or displays a bitmap
 * pushed from the MCP server.
 *
 * Note: NavigationTemplate is used as the root (not inside TabTemplate)
 * because the DHU screenshot mechanism does not capture the surface layer
 * when NavigationTemplate is embedded as tab content inside TabTemplate.
 * Agent conversation views will be added as pushed screens in a future PR.
 */
class VanPilotScreen(carContext: CarContext) : Screen(carContext) {

    val surfaceCallback = VanPilotSurfaceCallback()
    val tabManager = ConversationTabManager.createWithMockData()

    /** Whether the surface callback has been registered with the host. */
    private var surfaceCallbackRegistered = false

    /** Tracks the current dark mode state. */
    var currentIsDarkMode: Boolean = false
        private set

    /** Updates the theme based on dark mode state and propagates to surface callback. */
    fun updateTheme(isDarkMode: Boolean) {
        currentIsDarkMode = isDarkMode
        surfaceCallback.setTheme(DarkModeTheme.forDarkMode(isDarkMode))
    }

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
        const val LEAD_AGENT_TAB_ID = ConversationTabManager.LEAD_AGENT_TAB_ID
    }

    override fun onGetTemplate(): NavigationTemplate {
        // Register the surface callback on first template request.
        // Cannot do this in onCreateScreen() — the host connection
        // isn't established yet ("Could not retrieve host").
        if (!surfaceCallbackRegistered) {
            carContext.getCarService(AppManager::class.java)
                .setSurfaceCallback(surfaceCallback)
            surfaceCallbackRegistered = true
        }

        // Read dark mode state from the host on every template refresh.
        // onGetTemplate() is called on configuration changes, so this
        // picks up dark mode toggling automatically.
        updateTheme(carContext.isDarkMode)

        return NavigationTemplate.Builder()
            .setActionStrip(ActionStrip.Builder().addAction(Action.PAN).build())
            .build()
    }
}
