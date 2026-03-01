package com.vanpilot.auto

import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Action
import androidx.car.app.model.ActionStrip
import androidx.car.app.model.CarIcon
import androidx.car.app.model.Pane
import androidx.car.app.model.PaneTemplate
import androidx.car.app.model.Row
import androidx.car.app.model.Tab
import androidx.car.app.model.TabContents
import androidx.car.app.model.TabTemplate
import androidx.car.app.navigation.model.NavigationTemplate

/**
 * The main screen of the VanPilot Android Auto app.
 * Uses a TabTemplate with two tabs: a Visual tab embedding a NavigationTemplate
 * with a SurfaceCallback for custom rendering, and a Status tab showing app info.
 * TabTemplate requires a minimum of 2 tabs.
 */
class VanPilotScreen(carContext: CarContext) : Screen(carContext) {

    val surfaceCallback = VanPilotSurfaceCallback()

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
        const val STATUS_TAB_ID = "status_card"
    }

    override fun onGetTemplate(): TabTemplate {
        // Read dark mode state from the host on every template refresh.
        // onGetTemplate() is called on configuration changes, so this
        // picks up dark mode toggling automatically.
        updateTheme(carContext.isDarkMode)

        val navigationTemplate = NavigationTemplate.Builder()
            .setActionStrip(ActionStrip.Builder().addAction(Action.PAN).build())
            .build()

        val appIcon = CarIcon.Builder(CarIcon.APP_ICON).build()

        val visualTab = Tab.Builder()
            .setTitle("Visual")
            .setContentId(VISUAL_TAB_ID)
            .setIcon(appIcon)
            .build()

        val statusTab = Tab.Builder()
            .setTitle("Status")
            .setContentId(STATUS_TAB_ID)
            .setIcon(appIcon)
            .build()

        return TabTemplate.Builder(object : TabTemplate.TabCallback {
            override fun onTabSelected(tabContentId: String) {
                // Tab selection handling — no-op for now
            }
        })
            .setTabContents(TabContents.Builder(navigationTemplate).build())
            .addTab(visualTab)
            .addTab(statusTab)
            .setActiveTabContentId(VISUAL_TAB_ID)
            .setHeaderAction(Action.APP_ICON)
            .build()
    }
}
