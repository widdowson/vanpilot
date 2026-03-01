package com.vanpilot.auto

import androidx.car.app.Screen
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VanPilotScreen.
 * Verifies class structure and constants without requiring the full Android runtime.
 */
@RunWith(JUnit4::class)
class VanPilotScreenTest {

    @Test
    fun classExtendsScreen() {
        assertThat(Screen::class.java.isAssignableFrom(VanPilotScreen::class.java))
            .isTrue()
    }

    @Test
    fun visualTabIdConstant() {
        assertThat(VanPilotScreen.VISUAL_TAB_ID).isEqualTo("visual_card")
    }

    @Test
    fun onGetTemplate_declaredAsOverride() {
        val method = VanPilotScreen::class.java.getMethod("onGetTemplate")
        assertThat(method).isNotNull()
    }
}
