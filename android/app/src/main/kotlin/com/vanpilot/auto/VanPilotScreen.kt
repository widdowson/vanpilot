package com.vanpilot.auto

import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Tab
import androidx.car.app.model.TabContents
import androidx.car.app.model.TabTemplate
import androidx.car.app.navigation.model.NavigationTemplate

/**
 * The main screen of the VanPilot Android Auto app.
 * Uses a TabTemplate with one tab that embeds a NavigationTemplate
 * with a SurfaceCallback for custom rendering.
 */
class VanPilotScreen(carContext: CarContext) : Screen(carContext) {

    val surfaceCallback = VanPilotSurfaceCallback()

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
    }

    override fun onGetTemplate(): TabTemplate {
        val navigationTemplate = NavigationTemplate.Builder()
            .build()

        val visualTab = Tab.Builder()
            .setTitle("Visual")
            .setContentId(VISUAL_TAB_ID)
            .setIcon(
                androidx.car.app.model.CarIcon.Builder(
                    androidx.car.app.model.CarIcon.APP_ICON
                ).build()
            )
            .build()

        return TabTemplate.Builder(object : TabTemplate.TabCallback {
            override fun onTabSelected(tabContentId: String) {
                // Single tab for now; no-op
            }
        })
            .setTabContents(TabContents.Builder(navigationTemplate).build())
            .addTab(visualTab)
            .setActiveTabContentId(VISUAL_TAB_ID)
            .setHeaderAction(androidx.car.app.model.Action.APP_ICON)
            .build()
    }
}
