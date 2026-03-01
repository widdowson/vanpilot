package com.vanpilot.auto

import androidx.car.app.Session
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VanPilotSession.
 * Verifies class structure without requiring the full Android runtime.
 */
@RunWith(JUnit4::class)
class VanPilotSessionTest {

    @Test
    fun classExtendsSession() {
        assertThat(Session::class.java.isAssignableFrom(VanPilotSession::class.java))
            .isTrue()
    }

    @Test
    fun onCreateScreen_declaredAsOverride() {
        val method = VanPilotSession::class.java.getMethod("onCreateScreen", android.content.Intent::class.java)
        assertThat(method).isNotNull()
        assertThat(method.returnType.name).isEqualTo("androidx.car.app.Screen")
    }
}
