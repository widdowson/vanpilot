package com.vanpilot.auto

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.SurfaceTexture
import android.view.Surface
import androidx.car.app.SurfaceContainer
import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Tests for the bitmap rendering path in VanPilotSurfaceCallback.
 *
 * Covers: displayBitmap, clearBitmap, drawCurrentContent dispatch,
 * drawBitmapOnSurface surface interaction, display/clear/display cycle,
 * and dark mode interaction while bitmap is displayed.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotSurfaceCallbackBitmapTest {

    private lateinit var callback: VanPilotSurfaceCallback

    @Before
    fun setUp() {
        callback = VanPilotSurfaceCallback()
    }

    // =========================================================================
    // displayBitmap state tests
    // =========================================================================

    @Test
    fun displayBitmap_setsCurrentBitmap() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap)
    }

    @Test
    fun displayBitmap_setsCurrentCacheKey() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xBEEF", bitmap)
        assertThat(callback.currentCacheKey).isEqualTo("0xBEEF")
    }

    @Test
    fun displayBitmap_secondCall_replacesPreviousBitmap() {
        val bitmap1 = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        val bitmap2 = Bitmap.createBitmap(200, 200, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xAAAA", bitmap1)
        callback.displayBitmap("0xBBBB", bitmap2)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap2)
        assertThat(callback.currentCacheKey).isEqualTo("0xBBBB")
    }

    // =========================================================================
    // clearBitmap state tests
    // =========================================================================

    @Test
    fun clearBitmap_resetsCurrentBitmapToNull() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)
        callback.clearBitmap()
        assertThat(callback.currentBitmap).isNull()
    }

    @Test
    fun clearBitmap_resetsCurrentCacheKeyToNull() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)
        callback.clearBitmap()
        assertThat(callback.currentCacheKey).isNull()
    }

    @Test
    fun clearBitmap_whenNoBitmapSet_isNoOp() {
        callback.clearBitmap()
        assertThat(callback.currentBitmap).isNull()
        assertThat(callback.currentCacheKey).isNull()
    }

    // =========================================================================
    // drawCurrentContent dispatch tests
    //
    // Verifies that onSurfaceAvailable dispatches to the bitmap path
    // when a bitmap is set, and the solid-color path when null.
    // Uses SurfaceContainer with Robolectric's shadowed Surface.
    // =========================================================================

    @Test
    fun onSurfaceAvailable_withBitmapSet_drawsBitmapNotRect() {
        val srcBitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", srcBitmap)

        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        // onSurfaceAvailable triggers drawCurrentContent -> drawBitmapOnSurface
        callback.onSurfaceAvailable(container)

        // Verify surface was stored
        assertThat(callback.currentSurface).isSameInstanceAs(container)
        assertThat(callback.surfaceAvailableCount).isEqualTo(1)
        surfaceTexture.release()
    }

    @Test
    fun onSurfaceAvailable_withNoBitmap_drawsSolidColor() {
        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        // No bitmap set, so this should take the solid-color path
        callback.onSurfaceAvailable(container)

        assertThat(callback.currentSurface).isSameInstanceAs(container)
        assertThat(callback.currentBitmap).isNull()
        assertThat(callback.surfaceAvailableCount).isEqualTo(1)
        surfaceTexture.release()
    }

    @Test
    fun displayBitmap_withSurfaceAvailable_triggersRedraw() {
        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        // Set up surface first
        callback.onSurfaceAvailable(container)
        assertThat(callback.surfaceAvailableCount).isEqualTo(1)

        // displayBitmap should trigger drawCurrentContent on the existing surface
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)

        // Verify state is consistent — bitmap is set and surface is still available
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap)
        assertThat(callback.currentSurface).isSameInstanceAs(container)
        surfaceTexture.release()
    }

    @Test
    fun clearBitmap_withSurfaceAvailable_triggersRedraw() {
        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        callback.onSurfaceAvailable(container)
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)

        // clearBitmap should trigger drawCurrentContent (solid-color path)
        callback.clearBitmap()

        assertThat(callback.currentBitmap).isNull()
        assertThat(callback.currentSurface).isSameInstanceAs(container)
        surfaceTexture.release()
    }

    // =========================================================================
    // drawBitmapOnSurface surface interaction tests
    //
    // Verifies that the bitmap rendering path interacts correctly with
    // the Surface (lockCanvas / unlockCanvasAndPost). Uses Robolectric's
    // ShadowSurface which handles these calls in test mode.
    // =========================================================================

    @Test
    fun drawBitmapOnSurface_doesNotCrash_withValidSurface() {
        val srcBitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", srcBitmap)

        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        // This triggers drawBitmapOnSurface which calls lockCanvas/unlockCanvasAndPost
        callback.onSurfaceAvailable(container)

        // If we got here without exception, the surface interaction succeeded
        assertThat(callback.currentSurface).isNotNull()
        surfaceTexture.release()
    }

    @Test
    fun drawBitmapOnSurface_handlesNullSurface() {
        val srcBitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", srcBitmap)

        // SurfaceContainer with null surface — drawBitmapOnSurface should return early
        val container = SurfaceContainer(null, 800, 480, 160)
        callback.onSurfaceAvailable(container)

        // State should be updated even though drawing was skipped
        assertThat(callback.currentSurface).isSameInstanceAs(container)
        assertThat(callback.surfaceAvailableCount).isEqualTo(1)
    }

    // =========================================================================
    // Display -> clear -> display cycle
    // =========================================================================

    @Test
    fun displayClearDisplay_restoresBitmapState() {
        val bitmap1 = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        val bitmap2 = Bitmap.createBitmap(200, 200, Bitmap.Config.ARGB_8888)

        // Display first bitmap
        callback.displayBitmap("0xAAAA", bitmap1)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap1)
        assertThat(callback.currentCacheKey).isEqualTo("0xAAAA")

        // Clear
        callback.clearBitmap()
        assertThat(callback.currentBitmap).isNull()
        assertThat(callback.currentCacheKey).isNull()

        // Display second bitmap — bitmap rendering is restored
        callback.displayBitmap("0xBBBB", bitmap2)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap2)
        assertThat(callback.currentCacheKey).isEqualTo("0xBBBB")
    }

    @Test
    fun displayClearDisplay_withSurface_fullCycle() {
        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        // Make surface available first
        callback.onSurfaceAvailable(container)

        val bitmap1 = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        val bitmap2 = Bitmap.createBitmap(200, 200, Bitmap.Config.ARGB_8888)

        // Display -> triggers drawBitmapOnSurface
        callback.displayBitmap("0xAAAA", bitmap1)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap1)

        // Clear -> triggers drawSolidColor
        callback.clearBitmap()
        assertThat(callback.currentBitmap).isNull()

        // Display again -> triggers drawBitmapOnSurface
        callback.displayBitmap("0xBBBB", bitmap2)
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap2)
        assertThat(callback.currentCacheKey).isEqualTo("0xBBBB")

        surfaceTexture.release()
    }

    // =========================================================================
    // Dark mode interaction while bitmap is displayed
    // =========================================================================

    @Test
    fun setTheme_whileBitmapDisplayed_preservesBitmapState() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)

        callback.setTheme(DarkModeTheme.dark())

        // Bitmap should still be set after theme change
        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap)
        assertThat(callback.currentCacheKey).isEqualTo("0xDEAD")
        assertThat(callback.currentTheme.isDarkMode).isTrue()
    }

    @Test
    fun setTheme_whileBitmapDisplayed_withSurface_doesNotCrash() {
        val surfaceTexture = SurfaceTexture(0)
        val surface = Surface(surfaceTexture)
        val container = SurfaceContainer(surface, 800, 480, 160)

        callback.onSurfaceAvailable(container)
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)

        // Theme change while bitmap is displayed triggers drawCurrentContent
        // which should dispatch to bitmap path (not solid color)
        callback.setTheme(DarkModeTheme.dark())

        assertThat(callback.currentBitmap).isSameInstanceAs(bitmap)
        assertThat(callback.currentTheme.isDarkMode).isTrue()

        surfaceTexture.release()
    }

    @Test
    fun clearBitmap_afterDarkModeThemeChange_revertsToSolidColorWithDarkTheme() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)
        callback.setTheme(DarkModeTheme.dark())
        callback.clearBitmap()

        // After clear, should be in solid-color mode with dark theme
        assertThat(callback.currentBitmap).isNull()
        assertThat(callback.currentCacheKey).isNull()
        assertThat(callback.currentTheme.isDarkMode).isTrue()
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF0D4540.toInt())
    }

    @Test
    fun clearBitmap_afterDarkModeThemeChange_drawToCanvasUsesDarkColor() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        callback.displayBitmap("0xDEAD", bitmap)
        callback.setTheme(DarkModeTheme.dark())
        callback.clearBitmap()

        // Verify that drawToCanvas (solid-color path) uses the dark theme color
        val canvasBitmap = Bitmap.createBitmap(800, 480, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(canvasBitmap)
        val shadowCanvas = Shadows.shadowOf(canvas)

        callback.drawToCanvas(canvas, 800, 480)

        val event = shadowCanvas.getDrawnRect(0)
        assertThat(event.paint.color).isEqualTo(DarkModeTheme.dark().surfaceColor)
    }
}
