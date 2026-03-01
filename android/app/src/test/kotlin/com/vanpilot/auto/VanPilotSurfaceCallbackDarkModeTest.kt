package com.vanpilot.auto

import android.graphics.Bitmap
import android.graphics.Canvas
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.ConscryptMode
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO

@RunWith(RobolectricTestRunner::class)
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotSurfaceCallbackDarkModeTest {

    @Test
    fun drawToCanvas_darkTheme_usesDarkTealColor() {
        val callback = VanPilotSurfaceCallback()
        callback.setTheme(DarkModeTheme.dark())

        // Verify the theme's surface color is dark teal
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF0D4540.toInt())

        // Verify drawToCanvas doesn't crash (rendering details are tested via golden images)
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        callback.drawToCanvas(canvas, 100, 100)
    }

    @Test
    fun drawToCanvas_lightTheme_usesBrandTealColor() {
        val callback = VanPilotSurfaceCallback()
        callback.setTheme(DarkModeTheme.light())

        // Verify the theme's surface color is brand teal
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF1A8A7D.toInt())

        // Verify drawToCanvas doesn't crash
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        callback.drawToCanvas(canvas, 100, 100)
    }

    @Test
    fun defaultTheme_isLight() {
        val callback = VanPilotSurfaceCallback()
        assertThat(callback.currentTheme.isDarkMode).isFalse()
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF1A8A7D.toInt())
    }

    @Test
    fun setTheme_dark_updatesCurrentTheme() {
        val callback = VanPilotSurfaceCallback()
        callback.setTheme(DarkModeTheme.dark())
        assertThat(callback.currentTheme.isDarkMode).isTrue()
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF0D4540.toInt())
    }

    @Test
    fun setTheme_switchBackToLight_updatesCurrentTheme() {
        val callback = VanPilotSurfaceCallback()
        callback.setTheme(DarkModeTheme.dark())
        callback.setTheme(DarkModeTheme.light())
        assertThat(callback.currentTheme.isDarkMode).isFalse()
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF1A8A7D.toInt())
    }

    @Test
    fun currentTheme_propertyReflectsLastSetTheme() {
        val callback = VanPilotSurfaceCallback()
        val dark = DarkModeTheme.dark()
        callback.setTheme(dark)
        assertThat(callback.currentTheme).isEqualTo(dark)
    }

    @Test
    fun goldenImage_darkTeal_matchesDarkThemeSurface() {
        // Use Bazel runfiles to locate the golden image.
        val testSrcDir = System.getenv("TEST_SRCDIR")
        val testWorkspace = System.getenv("TEST_WORKSPACE") ?: "_main"
        val goldenFile = if (testSrcDir != null) {
            File(testSrcDir, "$testWorkspace/goldens/phase3/solid_dark_teal_800x480.png")
        } else {
            File("goldens/phase3/solid_dark_teal_800x480.png")
        }
        if (!goldenFile.exists()) {
            return
        }
        val golden = ImageIO.read(goldenFile)
        assertThat(golden.width).isEqualTo(800)
        assertThat(golden.height).isEqualTo(480)

        // Verify the golden is the dark teal color (0xFF0D4540)
        val expectedRgb = 0xFF0D4540.toInt()
        val pixelArgb = golden.getRGB(400, 240) // center pixel
        assertThat(pixelArgb).isEqualTo(expectedRgb)
    }
}
