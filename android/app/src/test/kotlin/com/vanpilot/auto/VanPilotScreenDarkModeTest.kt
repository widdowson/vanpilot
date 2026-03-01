package com.vanpilot.auto

import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.ConscryptMode

@RunWith(RobolectricTestRunner::class)
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenDarkModeTest {

    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val testCarContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        screen = VanPilotScreen(testCarContext)
    }

    @Test
    fun initialState_isLightMode() {
        assertThat(screen.currentIsDarkMode).isFalse()
    }

    @Test
    fun updateTheme_dark_setsCurrentIsDarkMode() {
        screen.updateTheme(isDarkMode = true)
        assertThat(screen.currentIsDarkMode).isTrue()
    }

    @Test
    fun updateTheme_light_setsCurrentIsDarkModeFalse() {
        screen.updateTheme(isDarkMode = true)
        screen.updateTheme(isDarkMode = false)
        assertThat(screen.currentIsDarkMode).isFalse()
    }

    @Test
    fun updateTheme_dark_propagatesToSurfaceCallback() {
        screen.updateTheme(isDarkMode = true)
        assertThat(screen.surfaceCallback.currentTheme.isDarkMode).isTrue()
        assertThat(screen.surfaceCallback.currentTheme.surfaceColor)
            .isEqualTo(DarkModeTheme.dark().surfaceColor)
    }

    @Test
    fun updateTheme_light_propagatesLightThemeToSurfaceCallback() {
        screen.updateTheme(isDarkMode = true)
        screen.updateTheme(isDarkMode = false)
        assertThat(screen.surfaceCallback.currentTheme.isDarkMode).isFalse()
        assertThat(screen.surfaceCallback.currentTheme.surfaceColor)
            .isEqualTo(DarkModeTheme.light().surfaceColor)
    }
}
