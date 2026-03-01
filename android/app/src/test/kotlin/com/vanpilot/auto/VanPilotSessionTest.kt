package com.vanpilot.auto

import android.content.Intent
import androidx.car.app.testing.SessionController
import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Behavioral tests for VanPilotSession.
 * Uses SessionController from the Car App Library testing framework.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotSessionTest {

    private lateinit var session: VanPilotSession
    private lateinit var controller: SessionController

    @Before
    fun setUp() {
        session = VanPilotSession()
        val testCarContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        controller = SessionController(session, testCarContext, Intent())
    }

    @Test
    fun onCreateScreen_returnsVanPilotScreen() {
        val screen = session.onCreateScreen(Intent())
        assertThat(screen).isInstanceOf(VanPilotScreen::class.java)
    }

    @Test
    fun onCreateScreen_screenHasSurfaceCallback() {
        val screen = session.onCreateScreen(Intent()) as VanPilotScreen
        assertThat(screen.surfaceCallback).isNotNull()
        assertThat(screen.surfaceCallback).isInstanceOf(VanPilotSurfaceCallback::class.java)
    }
}
