package com.vanpilot.auto

import android.graphics.BitmapFactory
import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Action
import androidx.car.app.model.ActionStrip
import androidx.car.app.model.CarColor
import androidx.car.app.model.CarIcon
import androidx.car.app.model.Header
import androidx.car.app.model.ItemList
import androidx.car.app.model.ListTemplate
import androidx.car.app.model.Row
import androidx.car.app.model.Tab
import androidx.car.app.model.TabContents
import androidx.car.app.model.TabTemplate
import androidx.car.app.navigation.model.NavigationTemplate
import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.cache.DisplayHistory
import com.vanpilot.auto.connectivity.ConnectionMonitor
import com.vanpilot.auto.connectivity.ConnectionState
import com.vanpilot.auto.voice.VoiceState
import com.vanpilot.auto.voice.VoiceStateMachine

/**
 * The main screen of the VanPilot Android Auto app.
 * Uses a TabTemplate with tabs:
 * - Visual Card: NavigationTemplate with SurfaceCallback for bitmap rendering
 * - Lead Agent: ListTemplate showing the lead agent's conversation feed
 * - Sub-Agent tabs: One ListTemplate per active sub-agent (up to 2)
 *
 * TabTemplate supports a maximum of 4 tabs total.
 */
class VanPilotScreen(
    carContext: CarContext,
    val connectionMonitor: ConnectionMonitor = ConnectionMonitor(),
    val voiceStateMachine: VoiceStateMachine? = null
) : Screen(carContext) {

    /**
     * Called when STT produces a final transcript. External code should
     * set this to trigger the gRPC SendUserInput call.
     */
    var onTranscriptionReady: ((String) -> Unit)? = null
        set(value) {
            field = value
            voiceStateMachine?.onTranscriptionReady = value
        }

    init {
        connectionMonitor.addListener { invalidate() }
    }

    val surfaceCallback = VanPilotSurfaceCallback()
    val tabManager = ConversationTabManager.createWithMockData()
    val displayHistory = DisplayHistory()
    var bitmapCache: BitmapCache? = null

    /** Tracks the current dark mode state. */
    var currentIsDarkMode: Boolean = false
        private set

    /** Updates the theme based on dark mode state and propagates to surface callback. */
    fun updateTheme(isDarkMode: Boolean) {
        currentIsDarkMode = isDarkMode
        surfaceCallback.setTheme(DarkModeTheme.forDarkMode(isDarkMode))
    }

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
        const val LEAD_AGENT_TAB_ID = ConversationTabManager.LEAD_AGENT_TAB_ID
    }

    /** The currently active tab content ID. Defaults to Visual tab. */
    private var activeTabId: String = VISUAL_TAB_ID

    /**
     * Handle tab selection: update active tab state and refresh the template.
     * Called by the TabCallback and also usable directly in tests.
     */
    fun selectTab(tabContentId: String) {
        activeTabId = tabContentId
        if (tabContentId != VISUAL_TAB_ID) {
            tabManager.activeConversationTabId = tabContentId
        } else {
            tabManager.activeConversationTabId = null
        }
        invalidate()
    }

    override fun onGetTemplate(): TabTemplate {
        // Read dark mode state from the host on every template refresh.
        // onGetTemplate() is called on configuration changes, so this
        // picks up dark mode toggling automatically.
        updateTheme(carContext.isDarkMode)

        val appIcon = CarIcon.Builder(CarIcon.APP_ICON).build()

        val builder = TabTemplate.Builder(object : TabTemplate.TabCallback {
            override fun onTabSelected(tabContentId: String) {
                selectTab(tabContentId)
            }
        })

        // Visual Card tab
        val visualTab = Tab.Builder()
            .setTitle("Visual")
            .setContentId(VISUAL_TAB_ID)
            .setIcon(appIcon)
            .build()
        builder.addTab(visualTab)

        // Lead Agent tab
        val leadTab = Tab.Builder()
            .setTitle("Lead Agent")
            .setContentId(LEAD_AGENT_TAB_ID)
            .setIcon(appIcon)
            .build()
        builder.addTab(leadTab)

        // Sub-Agent tabs (dynamic, capped by ConversationTabManager.MAX_SUB_AGENT_TABS)
        val validTabIds = mutableSetOf(VISUAL_TAB_ID, LEAD_AGENT_TAB_ID)
        for ((index, agentId) in tabManager.getSubAgentIds().withIndex()) {
            if (index >= ConversationTabManager.MAX_SUB_AGENT_TABS) break
            val tabId = ConversationTabManager.subAgentTabId(agentId)
            validTabIds.add(tabId)
            val subTab = Tab.Builder()
                .setTitle(agentId.replaceFirstChar { it.uppercase() })
                .setContentId(tabId)
                .setIcon(appIcon)
                .build()
            builder.addTab(subTab)
        }

        // Fall back to visual tab if activeTabId is stale or unrecognized
        val effectiveTabId = if (activeTabId in validTabIds) activeTabId else VISUAL_TAB_ID

        // Set active tab content
        val tabContents = when (effectiveTabId) {
            VISUAL_TAB_ID -> {
                val indicatorColor = when (connectionMonitor.state) {
                    ConnectionState.CONNECTED -> CarColor.GREEN
                    ConnectionState.DISCONNECTED -> CarColor.RED
                    ConnectionState.RECONNECTING -> CarColor.YELLOW
                }
                val indicatorIcon = CarIcon.Builder(CarIcon.APP_ICON)
                    .setTint(indicatorColor)
                    .build()
                val indicatorAction = Action.Builder()
                    .setIcon(indicatorIcon)
                    .setOnClickListener { }
                    .build()
                val actionStripBuilder = ActionStrip.Builder()
                    .addAction(indicatorAction)
                if (voiceStateMachine != null) {
                    actionStripBuilder.addAction(buildMicAction(voiceStateMachine))
                } else {
                    actionStripBuilder.addAction(Action.PAN)
                }
                actionStripBuilder
                    .addAction(buildBackAction())
                    .addAction(buildForwardAction())
                val navTemplate = NavigationTemplate.Builder()
                    .setActionStrip(actionStripBuilder.build())
                    .build()
                TabContents.Builder(navTemplate).build()
            }
            LEAD_AGENT_TAB_ID -> {
                TabContents.Builder(
                    buildMessageList(tabManager.getLeadAgentMessages(), "Lead Agent")
                ).build()
            }
            else -> {
                val agentId = ConversationTabManager.agentIdFromTabId(effectiveTabId)
                val messages = tabManager.getSubAgentMessages(agentId)
                TabContents.Builder(buildMessageList(messages, agentId)).build()
            }
        }

        builder.setTabContents(tabContents)
        builder.setActiveTabContentId(effectiveTabId)
        builder.setHeaderAction(Action.APP_ICON)

        return builder.build()
    }

    /**
     * Builds a ListTemplate from a list of conversation messages.
     * If no messages, shows a placeholder row.
     */
    private fun buildMessageList(
        messages: List<ConversationMessage>,
        title: String
    ): ListTemplate {
        val listBuilder = ItemList.Builder()

        if (messages.isEmpty()) {
            listBuilder.addItem(
                Row.Builder()
                    .setTitle("No messages yet")
                    .build()
            )
        } else {
            val displayMessages = messages.takeLast(ConversationTabManager.MAX_MESSAGES_PER_TAB)
            for (msg in displayMessages) {
                listBuilder.addItem(
                    Row.Builder()
                        .setTitle(msg.text)
                        .addText(msg.sender)
                        .build()
                )
            }
        }

        return ListTemplate.Builder()
            .setSingleList(listBuilder.build())
            .setHeader(Header.Builder().setTitle(title).build())
            .build()
    }

    private fun navigateHistory(key: String) {
        val cache = bitmapCache ?: return
        val pngData = cache.get(key) ?: return
        val bitmap = BitmapFactory.decodeByteArray(pngData, 0, pngData.size) ?: return
        surfaceCallback.displayBitmap(key, bitmap)
        invalidate()
    }

    private fun buildMicAction(vsm: VoiceStateMachine): Action {
        val state = vsm.currentState
        val isIdle = state == VoiceState.IDLE
        val isListening = state == VoiceState.LISTENING
        val enabled = isIdle || isListening
        val title = if (isListening) "\u23F9" else "\uD83C\uDF99"

        return Action.Builder()
            .setTitle(title)
            .setEnabled(enabled)
            .setOnClickListener {
                if (isListening) {
                    vsm.cancelListening()
                } else if (isIdle) {
                    vsm.activateVoice()
                }
                invalidate()
            }
            .build()
    }

    private fun buildBackAction(): Action {
        return Action.Builder()
            .setTitle("\u2190")
            .setEnabled(displayHistory.canGoBack())
            .setOnClickListener {
                val key = displayHistory.goBack()
                if (key != null) navigateHistory(key)
            }
            .build()
    }

    private fun buildForwardAction(): Action {
        return Action.Builder()
            .setTitle("\u2192")
            .setEnabled(displayHistory.canGoForward())
            .setOnClickListener {
                val key = displayHistory.goForward()
                if (key != null) navigateHistory(key)
            }
            .build()
    }
}
