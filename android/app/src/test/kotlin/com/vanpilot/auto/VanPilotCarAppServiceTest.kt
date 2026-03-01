package com.vanpilot.auto

import androidx.car.app.Session
import androidx.car.app.testing.TestCarContext
import androidx.car.app.validation.HostValidator
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Behavioral tests for VanPilotCarAppService.
 * Uses Robolectric to instantiate the actual service and verify its behavior.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotCarAppServiceTest {

    @Test
    fun createHostValidator_returnsAllowAllHosts() {
        val service = Robolectric.setupService(VanPilotCarAppService::class.java)
        val validator = service.createHostValidator()
        assertThat(validator).isEqualTo(HostValidator.ALLOW_ALL_HOSTS_VALIDATOR)
    }

    @Test
    fun onCreateSession_returnsVanPilotSession() {
        val service = Robolectric.setupService(VanPilotCarAppService::class.java)
        val session = service.onCreateSession()
        assertThat(session).isInstanceOf(VanPilotSession::class.java)
    }

    @Test
    fun onCreateSession_returnsNewSessionEachTime() {
        val service = Robolectric.setupService(VanPilotCarAppService::class.java)
        val session1 = service.onCreateSession()
        val session2 = service.onCreateSession()
        assertThat(session1).isNotSameInstanceAs(session2)
    }
}
