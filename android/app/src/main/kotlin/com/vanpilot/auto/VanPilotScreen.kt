package com.vanpilot.auto

import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Header
import androidx.car.app.model.ItemList
import androidx.car.app.model.ListTemplate
import androidx.car.app.model.Row
import androidx.car.app.model.Tab
import androidx.car.app.model.TabContents
import androidx.car.app.model.TabTemplate
import androidx.car.app.navigation.model.NavigationTemplate

/**
 * The main screen of the VanPilot Android Auto app.
 * Uses a TabTemplate with tabs:
 * - Visual Card: NavigationTemplate with SurfaceCallback for bitmap rendering
 * - Lead Agent: ListTemplate showing the lead agent's conversation feed
 * - Sub-Agent tabs: One ListTemplate per active sub-agent (up to 2)
 *
 * TabTemplate supports a maximum of 4 tabs total.
 */
class VanPilotScreen(carContext: CarContext) : Screen(carContext) {

    val surfaceCallback = VanPilotSurfaceCallback()
    val tabManager = ConversationTabManager.createWithMockData()

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
        const val LEAD_AGENT_TAB_ID = ConversationTabManager.LEAD_AGENT_TAB_ID
    }

    /** The currently active tab content ID. Defaults to Visual tab. */
    private var activeTabId: String = VISUAL_TAB_ID

    override fun onGetTemplate(): TabTemplate {
        val builder = TabTemplate.Builder(object : TabTemplate.TabCallback {
            override fun onTabSelected(tabContentId: String) {
                activeTabId = tabContentId
                if (tabContentId != VISUAL_TAB_ID) {
                    tabManager.activeConversationTabId = tabContentId
                } else {
                    tabManager.activeConversationTabId = null
                }
                invalidate()
            }
        })

        // Visual Card tab
        val visualTab = Tab.Builder()
            .setTitle("Visual")
            .setContentId(VISUAL_TAB_ID)
            .setIcon(
                androidx.car.app.model.CarIcon.Builder(
                    androidx.car.app.model.CarIcon.APP_ICON
                ).build()
            )
            .build()
        builder.addTab(visualTab)

        // Lead Agent tab
        val leadTab = Tab.Builder()
            .setTitle("Lead Agent")
            .setContentId(LEAD_AGENT_TAB_ID)
            .setIcon(
                androidx.car.app.model.CarIcon.Builder(
                    androidx.car.app.model.CarIcon.APP_ICON
                ).build()
            )
            .build()
        builder.addTab(leadTab)

        // Sub-Agent tabs (dynamic, capped by ConversationTabManager.MAX_SUB_AGENT_TABS)
        for ((index, agentId) in tabManager.getSubAgentIds().withIndex()) {
            if (index >= ConversationTabManager.MAX_SUB_AGENT_TABS) break
            val subTab = Tab.Builder()
                .setTitle(agentId.replaceFirstChar { it.uppercase() })
                .setContentId(ConversationTabManager.subAgentTabId(agentId))
                .setIcon(
                    androidx.car.app.model.CarIcon.Builder(
                        androidx.car.app.model.CarIcon.APP_ICON
                    ).build()
                )
                .build()
            builder.addTab(subTab)
        }

        // Set active tab content
        val tabContents = when (activeTabId) {
            VISUAL_TAB_ID -> {
                val navTemplate = NavigationTemplate.Builder().build()
                TabContents.Builder(navTemplate).build()
            }
            LEAD_AGENT_TAB_ID -> {
                TabContents.Builder(
                    buildMessageList(tabManager.getLeadAgentMessages(), "Lead Agent")
                ).build()
            }
            else -> {
                val agentId = activeTabId.removePrefix("sub_agent_")
                val messages = tabManager.getSubAgentMessages(agentId)
                TabContents.Builder(buildMessageList(messages, agentId)).build()
            }
        }

        builder.setTabContents(tabContents)
        builder.setActiveTabContentId(activeTabId)
        builder.setHeaderAction(androidx.car.app.model.Action.APP_ICON)

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
            val displayMessages = messages.takeLast(100)
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
}
