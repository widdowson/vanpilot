package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.ConscryptMode

@RunWith(RobolectricTestRunner::class)
@ConscryptMode(ConscryptMode.Mode.OFF)
class DarkModeThemeTest {

    @Test
    fun lightTheme_isDarkModeFalse() {
        val theme = DarkModeTheme.light()
        assertThat(theme.isDarkMode).isFalse()
    }

    @Test
    fun darkTheme_isDarkModeTrue() {
        val theme = DarkModeTheme.dark()
        assertThat(theme.isDarkMode).isTrue()
    }

    @Test
    fun lightTheme_surfaceColor_isBrandTeal() {
        val theme = DarkModeTheme.light()
        assertThat(theme.surfaceColor).isEqualTo(0xFF1A8A7D.toInt())
    }

    @Test
    fun darkTheme_surfaceColor_isDarkTeal() {
        val theme = DarkModeTheme.dark()
        assertThat(theme.surfaceColor).isEqualTo(0xFF0D4540.toInt())
    }

    @Test
    fun lightTheme_textColor_isDark() {
        val theme = DarkModeTheme.light()
        assertThat(theme.textColor).isEqualTo(0xFF1B1B1B.toInt())
    }

    @Test
    fun darkTheme_textColor_isLight() {
        val theme = DarkModeTheme.dark()
        assertThat(theme.textColor).isEqualTo(0xFFE0E0E0.toInt())
    }

    @Test
    fun forDarkMode_true_returnsDarkTheme() {
        val theme = DarkModeTheme.forDarkMode(true)
        assertThat(theme.isDarkMode).isTrue()
        assertThat(theme.surfaceColor).isEqualTo(DarkModeTheme.dark().surfaceColor)
    }

    @Test
    fun forDarkMode_false_returnsLightTheme() {
        val theme = DarkModeTheme.forDarkMode(false)
        assertThat(theme.isDarkMode).isFalse()
        assertThat(theme.surfaceColor).isEqualTo(DarkModeTheme.light().surfaceColor)
    }

    @Test
    fun lightAndDark_haveDifferentSurfaceColors() {
        assertThat(DarkModeTheme.light().surfaceColor)
            .isNotEqualTo(DarkModeTheme.dark().surfaceColor)
    }

    @Test
    fun lightAndDark_haveDifferentTextColors() {
        assertThat(DarkModeTheme.light().textColor)
            .isNotEqualTo(DarkModeTheme.dark().textColor)
    }
}
