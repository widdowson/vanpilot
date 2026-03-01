package com.vanpilot.auto

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.util.Log
import androidx.car.app.SurfaceCallback
import androidx.car.app.SurfaceContainer

/**
 * Handles the raw Surface provided by the NavigationTemplate.
 *
 * Supports two rendering modes:
 * 1. Default: draws a solid teal rectangle (brand color for golden verification)
 * 2. Bitmap: draws a received bitmap scaled to fill the surface
 */
class VanPilotSurfaceCallback : SurfaceCallback {

    companion object {
        const val TAG = "VanPilotSurface"
    }

    /** The most recently provided surface container, or null if destroyed. */
    var currentSurface: SurfaceContainer? = null
        private set

    /** The visible area reported by the host, or null if not yet known. */
    var visibleArea: Rect? = null
        private set

    /** The stable area reported by the host, or null if not yet known. */
    var stableArea: Rect? = null
        private set

    /** Tracks whether onSurfaceAvailable has been called at least once. */
    var surfaceAvailableCount: Int = 0
        private set

    /** Current theme for rendering. Defaults to light mode. */
    var currentTheme: DarkModeTheme = DarkModeTheme.light()
        private set


    var currentBitmap: Bitmap? = null
        private set
    var currentCacheKey: String? = null
        private set

    /** Update the rendering theme. Redraws the surface if available. */
    fun setTheme(theme: DarkModeTheme) {
        currentTheme = theme
        Log.i(TAG, "Theme changed: isDarkMode=${theme.isDarkMode}")
        currentSurface?.let { drawCurrentContent(it) }
    }


    override fun onSurfaceAvailable(surfaceContainer: SurfaceContainer) {
        Log.i(TAG, "Surface available: ${surfaceContainer.width}x${surfaceContainer.height} " +
                "dpi=${surfaceContainer.dpi}")
        currentSurface = surfaceContainer
        surfaceAvailableCount++
        drawCurrentContent(surfaceContainer)
    }

    override fun onVisibleAreaChanged(visibleArea: Rect) {
        Log.i(TAG, "Visible area changed: $visibleArea")
        this.visibleArea = visibleArea
        currentSurface?.let { drawCurrentContent(it) }
    }

    override fun onStableAreaChanged(stableArea: Rect) {
        Log.i(TAG, "Stable area changed: $stableArea")
        this.stableArea = stableArea
    }

    override fun onSurfaceDestroyed(surfaceContainer: SurfaceContainer) {
        Log.i(TAG, "Surface destroyed")
        currentSurface = null
    }

    fun displayBitmap(cacheKey: String, bitmap: Bitmap) {
        currentBitmap = bitmap
        currentCacheKey = cacheKey
        currentSurface?.let { drawCurrentContent(it) }
    }

    fun clearBitmap() {
        currentBitmap = null
        currentCacheKey = null
        currentSurface?.let { drawCurrentContent(it) }
    }

    /**
     * Draws the VanPilot teal fill onto the given Canvas.
     * Extracted for testability — called by both the live surface path and golden tests.
     */
    fun drawToCanvas(canvas: Canvas, width: Int, height: Int) {
        val paint = Paint().apply {
            color = currentTheme.surfaceColor
            style = Paint.Style.FILL
        }
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
    }

    private fun drawCurrentContent(surfaceContainer: SurfaceContainer) {
        val bitmap = currentBitmap
        if (bitmap != null) {
            drawBitmapOnSurface(surfaceContainer, bitmap)
        } else {
            drawSolidColor(surfaceContainer)
        }
    }

    private fun drawBitmapOnSurface(surfaceContainer: SurfaceContainer, bitmap: Bitmap) {
        val surface = surfaceContainer.surface ?: return
        val canvas: Canvas = surface.lockCanvas(null) ?: return
        try {
            canvas.drawColor(Color.BLACK)
            val destRect = Rect(0, 0, canvas.width, canvas.height)
            canvas.drawBitmap(bitmap, null, destRect, null)
        } finally {
            surface.unlockCanvasAndPost(canvas)
        }
    }

    /**
     * Draws a solid color rectangle filling the entire surface.
     * This is the minimum viable proof that SurfaceCallback rendering works.
     */
    private fun drawSolidColor(surfaceContainer: SurfaceContainer) {
        val surface = surfaceContainer.surface ?: return
        val canvas: Canvas = surface.lockCanvas(null) ?: return
        try {
            drawToCanvas(canvas, canvas.width, canvas.height)
        } finally {
            surface.unlockCanvasAndPost(canvas)
        }
    }
}
