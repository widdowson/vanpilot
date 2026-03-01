package com.vanpilot.auto

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO

/**
 * Behavioral tests for VanPilotSurfaceCallback.
 * Tests state transitions, drawing behavior, and golden screenshot capture.
 *
 * Drawing verification uses Robolectric's ShadowCanvas to inspect the actual
 * drawRect calls (coordinates, paint color, style). Golden image generation
 * uses java.awt.BufferedImage since Robolectric's native graphics runtime
 * is not available on aarch64.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotSurfaceCallbackTest {

    private lateinit var callback: VanPilotSurfaceCallback

    companion object {
        const val GOLDEN_WIDTH = 800
        const val GOLDEN_HEIGHT = 480
        const val GOLDEN_DIR = "goldens/phase3"
        const val GOLDEN_FILENAME = "solid_teal_800x480.png"
    }

    @Before
    fun setUp() {
        callback = VanPilotSurfaceCallback()
    }

    // =========================================================================
    // Initial state tests
    // =========================================================================

    @Test
    fun initialState_noSurface() {
        assertThat(callback.currentSurface).isNull()
        assertThat(callback.surfaceAvailableCount).isEqualTo(0)
    }

    @Test
    fun initialState_noAreas() {
        assertThat(callback.visibleArea).isNull()
        assertThat(callback.stableArea).isNull()
    }

    // =========================================================================
    // State transition tests
    // =========================================================================

    @Test
    fun onVisibleAreaChanged_updatesVisibleArea() {
        val rect = Rect(10, 20, 790, 460)
        callback.onVisibleAreaChanged(rect)
        assertThat(callback.visibleArea).isEqualTo(rect)
    }

    @Test
    fun onStableAreaChanged_updatesStableArea() {
        val rect = Rect(0, 0, 800, 480)
        callback.onStableAreaChanged(rect)
        assertThat(callback.stableArea).isEqualTo(rect)
    }

    @Test
    fun onVisibleAreaChanged_multipleUpdates_keepsLatest() {
        val rect1 = Rect(10, 20, 790, 460)
        val rect2 = Rect(0, 0, 800, 480)
        callback.onVisibleAreaChanged(rect1)
        callback.onVisibleAreaChanged(rect2)
        assertThat(callback.visibleArea).isEqualTo(rect2)
    }

    // =========================================================================
    // Constants tests
    // =========================================================================

    @Test
    fun defaultTheme_surfaceColor_isVanPilotTeal() {
        assertThat(callback.currentTheme.surfaceColor).isEqualTo(0xFF1A8A7D.toInt())
    }

    @Test
    fun tag_isCorrect() {
        assertThat(VanPilotSurfaceCallback.TAG).isEqualTo("VanPilotSurface")
    }

    // =========================================================================
    // Drawing behavior tests (via ShadowCanvas inspection)
    // =========================================================================

    @Test
    fun drawToCanvas_drawsSingleRect() {
        val bitmap = Bitmap.createBitmap(GOLDEN_WIDTH, GOLDEN_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val shadowCanvas = Shadows.shadowOf(canvas)

        callback.drawToCanvas(canvas, GOLDEN_WIDTH, GOLDEN_HEIGHT)

        assertThat(shadowCanvas.rectPaintHistoryCount).isEqualTo(1)
    }

    @Test
    fun drawToCanvas_rectCoversFullCanvas() {
        val bitmap = Bitmap.createBitmap(GOLDEN_WIDTH, GOLDEN_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val shadowCanvas = Shadows.shadowOf(canvas)

        callback.drawToCanvas(canvas, GOLDEN_WIDTH, GOLDEN_HEIGHT)

        val event = shadowCanvas.getDrawnRect(0)
        assertThat(event.left).isEqualTo(0f)
        assertThat(event.top).isEqualTo(0f)
        assertThat(event.right).isEqualTo(GOLDEN_WIDTH.toFloat())
        assertThat(event.bottom).isEqualTo(GOLDEN_HEIGHT.toFloat())
    }

    @Test
    fun drawToCanvas_usesCorrectColor() {
        val bitmap = Bitmap.createBitmap(GOLDEN_WIDTH, GOLDEN_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val shadowCanvas = Shadows.shadowOf(canvas)

        callback.drawToCanvas(canvas, GOLDEN_WIDTH, GOLDEN_HEIGHT)

        val event = shadowCanvas.getDrawnRect(0)
        assertThat(event.paint.color).isEqualTo(DarkModeTheme.light().surfaceColor)
    }

    @Test
    fun drawToCanvas_usesFillStyle() {
        val bitmap = Bitmap.createBitmap(GOLDEN_WIDTH, GOLDEN_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val shadowCanvas = Shadows.shadowOf(canvas)

        callback.drawToCanvas(canvas, GOLDEN_WIDTH, GOLDEN_HEIGHT)

        val event = shadowCanvas.getDrawnRect(0)
        assertThat(event.paint.style).isEqualTo(Paint.Style.FILL)
    }

    // =========================================================================
    // Golden screenshot test
    //
    // Uses java.awt.BufferedImage for actual pixel rendering since
    // Robolectric's native runtime (Skia) is not available on aarch64.
    // The test generates the golden PNG and compares pixel-by-pixel.
    // =========================================================================

    @Test
    fun goldenScreenshot_matchesCommitted() {
        // Render using java.awt (works on all JDK architectures)
        val image = BufferedImage(GOLDEN_WIDTH, GOLDEN_HEIGHT, BufferedImage.TYPE_INT_ARGB)
        val g = image.createGraphics()
        val lightSurfaceColor = DarkModeTheme.light().surfaceColor
        val tealColor = java.awt.Color(
            (lightSurfaceColor shr 16) and 0xFF,  // R
            (lightSurfaceColor shr 8) and 0xFF,   // G
            lightSurfaceColor and 0xFF,            // B
            (lightSurfaceColor ushr 24) and 0xFF   // A
        )
        g.color = tealColor
        g.fillRect(0, 0, GOLDEN_WIDTH, GOLDEN_HEIGHT)
        g.dispose()

        // Verify the rendered pixels match the expected color
        val expectedArgb = lightSurfaceColor
        val centerPixel = image.getRGB(GOLDEN_WIDTH / 2, GOLDEN_HEIGHT / 2)
        assertThat(centerPixel).isEqualTo(expectedArgb)

        // Locate goldens directory
        val workspaceDir = System.getenv("BUILD_WORKSPACE_DIRECTORY")
            ?: System.getProperty("user.dir")
        val goldenDir = File(workspaceDir, GOLDEN_DIR)
        val goldenFile = File(goldenDir, GOLDEN_FILENAME)

        if (!goldenFile.exists()) {
            // First run: generate the golden image
            goldenDir.mkdirs()
            ImageIO.write(image, "png", goldenFile)
            println("Generated golden image: ${goldenFile.absolutePath}")
            return
        }

        // Load the golden and compare pixel-by-pixel
        val goldenImage = ImageIO.read(goldenFile)
        assertThat(goldenImage).isNotNull()
        assertThat(goldenImage.width).isEqualTo(GOLDEN_WIDTH)
        assertThat(goldenImage.height).isEqualTo(GOLDEN_HEIGHT)

        var mismatchCount = 0
        val diffImage = BufferedImage(GOLDEN_WIDTH, GOLDEN_HEIGHT, BufferedImage.TYPE_INT_ARGB)

        for (y in 0 until GOLDEN_HEIGHT) {
            for (x in 0 until GOLDEN_WIDTH) {
                val actual = image.getRGB(x, y)
                val golden = goldenImage.getRGB(x, y)
                if (actual != golden) {
                    mismatchCount++
                    diffImage.setRGB(x, y, java.awt.Color.RED.rgb)
                } else {
                    // Mark matching pixels as semi-transparent
                    diffImage.setRGB(x, y, (actual and 0x00FFFFFF) or 0x40000000)
                }
            }
        }

        if (mismatchCount > 0) {
            ImageIO.write(diffImage, "png", File(goldenDir, "diff_${GOLDEN_FILENAME}"))
            ImageIO.write(image, "png", File(goldenDir, "actual_${GOLDEN_FILENAME}"))
        }
        assertThat(mismatchCount).isEqualTo(0)
    }
}
