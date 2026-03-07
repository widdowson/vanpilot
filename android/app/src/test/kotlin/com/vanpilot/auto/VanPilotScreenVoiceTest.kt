package com.vanpilot.auto

import androidx.car.app.model.ActionStrip
import androidx.car.app.navigation.model.NavigationTemplate
import androidx.car.app.testing.TestCarContext
import androidx.test.core.app.ApplicationProvider
import androidx.car.app.OnDoneCallback
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.voice.FakeSttEngine
import com.vanpilot.auto.voice.FakeTtsEngine
import com.vanpilot.auto.voice.VoiceState
import com.vanpilot.auto.voice.VoiceStateMachine
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Tests for voice I/O wiring into VanPilotScreen.
 * Verifies that the VoiceStateMachine is properly connected to the UI:
 * - Mic action in the Visual tab action strip
 * - Tapping mic toggles IDLE↔LISTENING
 * - Voice state reflected in action strip
 * - Transcription callback fires
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VanPilotScreenVoiceTest {

    private lateinit var sttEngine: FakeSttEngine
    private lateinit var ttsEngine: FakeTtsEngine
    private lateinit var voiceStateMachine: VoiceStateMachine
    private lateinit var screen: VanPilotScreen

    @Before
    fun setUp() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        sttEngine = FakeSttEngine()
        ttsEngine = FakeTtsEngine()
        voiceStateMachine = VoiceStateMachine(sttEngine, ttsEngine)
        screen = VanPilotScreen(carContext, voiceStateMachine = voiceStateMachine)
    }

    // -- Voice state machine is wired --

    @Test
    fun voiceStateMachine_isAccessible() {
        assertThat(screen.voiceStateMachine).isSameInstanceAs(voiceStateMachine)
    }

    @Test
    fun voiceStateMachine_initialStateIsIdle() {
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    // -- Mic action in action strip --

    @Test
    fun visualTab_actionStrip_hasMicAction() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction).isNotNull()
    }

    @Test
    fun micAction_titleShowsMicWhenIdle() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.title.toString()).isEqualTo("\uD83C\uDF99")
    }

    @Test
    fun micAction_titleShowsStopWhenListening() {
        voiceStateMachine.activateVoice()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.title.toString()).isEqualTo("\u23F9")
    }

    // -- Mic click behavior --

    @Test
    fun micClick_fromIdle_activatesVoice() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        micAction!!.onClickDelegate!!.sendClick(object : OnDoneCallback {})
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.LISTENING)
    }

    @Test
    fun micClick_fromListening_cancelsListening() {
        voiceStateMachine.activateVoice()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        micAction!!.onClickDelegate!!.sendClick(object : OnDoneCallback {})
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.IDLE)
    }

    @Test
    fun micClick_fromIdle_startsSttEngine() {
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        micAction!!.onClickDelegate!!.sendClick(object : OnDoneCallback {})
        assertThat(sttEngine.startCount).isEqualTo(1)
    }

    // -- Mic is disabled during PROCESSING and SPEAKING --

    @Test
    fun micAction_disabledDuringProcessing() {
        voiceStateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.PROCESSING)
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.isEnabled).isFalse()
    }

    @Test
    fun micAction_disabledDuringSpeaking() {
        voiceStateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        voiceStateMachine.onResponseReceived("response")
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.SPEAKING)
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.isEnabled).isFalse()
    }

    @Test
    fun micAction_disabledWhenVoiceDisabled() {
        voiceStateMachine.disable()
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.isEnabled).isFalse()
    }

    @Test
    fun micAction_enabledAfterFullRoundTrip() {
        voiceStateMachine.activateVoice()
        sttEngine.simulateResult("hello")
        voiceStateMachine.onResponseReceived("Hi!")
        ttsEngine.simulateCompletion()
        assertThat(voiceStateMachine.currentState).isEqualTo(VoiceState.IDLE)
        val template = screen.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction!!.isEnabled).isTrue()
    }

    // -- Transcription callback --

    @Test
    fun onTranscriptionReady_firesWhenSttCompletes() {
        var received: String? = null
        screen.onTranscriptionReady = { received = it }
        voiceStateMachine.activateVoice()
        sttEngine.simulateResult("navigate home")
        assertThat(received).isEqualTo("navigate home")
    }

    // -- Screen without voice (backwards compatibility) --

    @Test
    fun screenWithoutVoice_noMicAction() {
        val carContext = TestCarContext.createCarContext(
            ApplicationProvider.getApplicationContext()
        )
        val screenNoVoice = VanPilotScreen(carContext)
        val template = screenNoVoice.onGetTemplate()
        val navTemplate = template.tabContents!!.template as NavigationTemplate
        val actionStrip = navTemplate.actionStrip!!
        val micAction = findMicAction(actionStrip)
        assertThat(micAction).isNull()
    }

    /**
     * Find the mic action in the action strip by checking for the mic/stop titles.
     */
    private fun findMicAction(actionStrip: ActionStrip): androidx.car.app.model.Action? {
        return actionStrip.actions.firstOrNull { action ->
            val title = action.title?.toString() ?: ""
            title == "\uD83C\uDF99" || title == "\u23F9"
        }
    }
}
