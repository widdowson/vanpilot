package com.vanpilot.auto

/**
 * Holds the color palette for light and dark mode rendering.
 * Used by VanPilotSurfaceCallback to choose surface and text colors.
 */
data class DarkModeTheme(
    val isDarkMode: Boolean,
    val surfaceColor: Int,
    val textColor: Int
) {
    companion object {
        /** Light mode: brand teal surface, dark text. */
        fun light() = DarkModeTheme(
            isDarkMode = false,
            surfaceColor = 0xFF1A8A7D.toInt(),
            textColor = 0xFF1B1B1B.toInt()
        )

        /** Dark mode: darker teal surface, light text. */
        fun dark() = DarkModeTheme(
            isDarkMode = true,
            surfaceColor = 0xFF0D4540.toInt(),
            textColor = 0xFFE0E0E0.toInt()
        )

        /** Factory: returns the appropriate theme for the given dark mode flag. */
        fun forDarkMode(isDark: Boolean): DarkModeTheme =
            if (isDark) dark() else light()
    }
}
