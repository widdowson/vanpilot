package com.vanpilot.auto

/**
 * Manages conversation data for the lead agent and sub-agent tabs.
 *
 * Holds messages per agent and provides methods to build tab content.
 * TabTemplate supports a maximum of 4 tabs total (1 Visual + 1 Lead Agent + up to 2 sub-agents,
 * or 1 Visual + up to 3 sub-agents if lead agent tab is not shown).
 * We reserve 1 tab for Visual and 1 for Lead Agent, leaving up to MAX_SUB_AGENT_TABS for sub-agents.
 */
class ConversationTabManager {

    companion object {
        const val LEAD_AGENT_TAB_ID = "lead_agent"
        const val MAX_SUB_AGENT_TABS = 3

        fun subAgentTabId(agentId: String): String = "sub_agent_$agentId"

        /**
         * Creates a ConversationTabManager pre-populated with mock data
         * for development and testing purposes.
         */
        fun createWithMockData(): ConversationTabManager {
            val manager = ConversationTabManager()

            // Lead agent mock messages
            manager.addLeadAgentMessage(
                ConversationMessage("lead", "Starting analysis of the codebase...", 1000L)
            )
            manager.addLeadAgentMessage(
                ConversationMessage("lead", "Found 3 potential issues in the auth module.", 2000L)
            )
            manager.addLeadAgentMessage(
                ConversationMessage("lead", "Delegating fix to researcher agent.", 3000L)
            )

            // Sub-agent: researcher
            manager.addSubAgent("researcher")
            manager.addSubAgentMessage(
                "researcher",
                ConversationMessage("researcher", "Investigating auth token expiry logic.", 1500L)
            )
            manager.addSubAgentMessage(
                "researcher",
                ConversationMessage("researcher", "Root cause: token refresh not retried on 503.", 2500L)
            )

            // Sub-agent: coder
            manager.addSubAgent("coder")
            manager.addSubAgentMessage(
                "coder",
                ConversationMessage("coder", "Implementing retry logic for token refresh.", 3500L)
            )

            return manager
        }
    }

    private val leadAgentMessages = mutableListOf<ConversationMessage>()
    private val subAgentOrder = mutableListOf<String>()
    private val subAgentMessages = mutableMapOf<String, MutableList<ConversationMessage>>()

    /** Currently active conversation tab ID, or null if no conversation tab is active. */
    var activeConversationTabId: String? = null

    // =========================================================================
    // Lead agent
    // =========================================================================

    fun getLeadAgentMessages(): List<ConversationMessage> = leadAgentMessages.toList()

    fun addLeadAgentMessage(message: ConversationMessage) {
        leadAgentMessages.add(message)
    }

    // =========================================================================
    // Sub-agents
    // =========================================================================

    fun getSubAgentIds(): List<String> = subAgentOrder.toList()

    fun addSubAgent(agentId: String) {
        if (agentId in subAgentOrder) return
        if (subAgentOrder.size >= MAX_SUB_AGENT_TABS) return
        subAgentOrder.add(agentId)
        subAgentMessages[agentId] = mutableListOf()
    }

    fun removeSubAgent(agentId: String) {
        subAgentOrder.remove(agentId)
        subAgentMessages.remove(agentId)
    }

    fun getSubAgentMessages(agentId: String): List<ConversationMessage> {
        return subAgentMessages[agentId]?.toList() ?: emptyList()
    }

    fun addSubAgentMessage(agentId: String, message: ConversationMessage) {
        subAgentMessages[agentId]?.add(message)
    }

    // =========================================================================
    // Tab IDs
    // =========================================================================

    fun getAllConversationTabIds(): List<String> {
        return buildList {
            add(LEAD_AGENT_TAB_ID)
            for (agentId in subAgentOrder) {
                add(subAgentTabId(agentId))
            }
        }
    }
}
