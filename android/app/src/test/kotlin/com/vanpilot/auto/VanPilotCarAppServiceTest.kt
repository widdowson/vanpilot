package com.vanpilot.auto

import androidx.car.app.CarAppService
import androidx.car.app.validation.HostValidator
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for VanPilotCarAppService.
 * Verifies class structure and constants without requiring the full Android runtime.
 */
@RunWith(JUnit4::class)
class VanPilotCarAppServiceTest {

    @Test
    fun classExtendsCarAppService() {
        assertThat(CarAppService::class.java.isAssignableFrom(VanPilotCarAppService::class.java))
            .isTrue()
    }

    @Test
    fun onCreateSession_declaredAsOverride() {
        // Verify the method exists and is callable via reflection
        val method = VanPilotCarAppService::class.java.getMethod("onCreateSession")
        assertThat(method).isNotNull()
        assertThat(method.returnType.name).isEqualTo("androidx.car.app.Session")
    }

    @Test
    fun createHostValidator_declaredAsOverride() {
        val method = VanPilotCarAppService::class.java.getMethod("createHostValidator")
        assertThat(method).isNotNull()
        assertThat(method.returnType.name).isEqualTo("androidx.car.app.validation.HostValidator")
    }
}
