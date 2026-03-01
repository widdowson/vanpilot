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
 * 1. Default: draws a solid teal rectangle
 * 2. Bitmap: draws a received bitmap scaled to fill the surface
 */
class VanPilotSurfaceCallback : SurfaceCallback {

    companion object {
        const val TAG = "VanPilotSurface"
        const val FILL_COLOR = 0xFF1A8A7D.toInt()
    }

    var currentSurface: SurfaceContainer? = null
        private set
    var visibleArea: Rect? = null
        private set
    var stableArea: Rect? = null
        private set
    var surfaceAvailableCount: Int = 0
        private set
    var currentBitmap: Bitmap? = null
        private set
    var currentCacheKey: String? = null
        private set

    override fun onSurfaceAvailable(surfaceContainer: SurfaceContainer) {
        Log.i(TAG, "Surface available: ${surfaceContainer.width}x${surfaceContainer.height} dpi=${surfaceContainer.dpi}")
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

    private fun drawSolidColor(surfaceContainer: SurfaceContainer) {
        val surface = surfaceContainer.surface ?: return
        val canvas: Canvas = surface.lockCanvas(null) ?: return
        try {
            val paint = Paint().apply {
                color = FILL_COLOR
                style = Paint.Style.FILL
            }
            canvas.drawRect(0f, 0f, canvas.width.toFloat(), canvas.height.toFloat(), paint)
        } finally {
            surface.unlockCanvasAndPost(canvas)
        }
    }
}
