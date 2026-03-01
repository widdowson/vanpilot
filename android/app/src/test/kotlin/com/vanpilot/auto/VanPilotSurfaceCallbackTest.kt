package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VanPilotSurfaceCallback.
 * Tests pure Kotlin state management without requiring the Android runtime.
 *
 * Tests that exercise Android framework classes (Rect, SurfaceContainer)
 * require Robolectric which needs Conscrypt aarch64 native libraries not
 * available in this sandbox. Those tests should be added when running on
 * x86_64 or when Robolectric adds aarch64 Conscrypt support.
 */
@RunWith(JUnit4::class)
class VanPilotSurfaceCallbackTest {

    private lateinit var callback: VanPilotSurfaceCallback

    @Before
    fun setUp() {
        callback = VanPilotSurfaceCallback()
    }

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

    @Test
    fun fillColor_isVanPilotTeal() {
        // Verify the fill color is our brand teal: #1A8A7D (fully opaque)
        assertThat(VanPilotSurfaceCallback.FILL_COLOR).isEqualTo(0xFF1A8A7D.toInt())
    }

    @Test
    fun tag_isCorrect() {
        assertThat(VanPilotSurfaceCallback.TAG).isEqualTo("VanPilotSurface")
    }
}
