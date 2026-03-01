package com.vanpilot.auto

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for ConversationTabManager.
 * Tests tab management, message storage, and sub-agent lifecycle.
 */
@RunWith(JUnit4::class)
class ConversationTabManagerTest {

    private lateinit var manager: ConversationTabManager

    @Before
    fun setUp() {
        manager = ConversationTabManager()
    }

    // =========================================================================
    // Lead agent tab ID
    // =========================================================================

    @Test
    fun leadAgentTabId_isConstant() {
        assertThat(ConversationTabManager.LEAD_AGENT_TAB_ID).isEqualTo("lead_agent")
    }

    @Test
    fun maxSubAgentTabs_isThree() {
        assertThat(ConversationTabManager.MAX_SUB_AGENT_TABS).isEqualTo(3)
    }

    // =========================================================================
    // Lead agent messages
    // =========================================================================

    @Test
    fun leadAgentMessages_initiallyEmpty() {
        assertThat(manager.getLeadAgentMessages()).isEmpty()
    }

    @Test
    fun addLeadAgentMessage_storesMessage() {
        val msg = ConversationMessage("lead", "Hello", 1000L)
        manager.addLeadAgentMessage(msg)
        assertThat(manager.getLeadAgentMessages()).containsExactly(msg)
    }

    @Test
    fun addMultipleLeadAgentMessages_preservesOrder() {
        val msg1 = ConversationMessage("lead", "First", 1000L)
        val msg2 = ConversationMessage("lead", "Second", 2000L)
        val msg3 = ConversationMessage("lead", "Third", 3000L)
        manager.addLeadAgentMessage(msg1)
        manager.addLeadAgentMessage(msg2)
        manager.addLeadAgentMessage(msg3)
        assertThat(manager.getLeadAgentMessages()).containsExactly(msg1, msg2, msg3).inOrder()
    }

    // =========================================================================
    // Sub-agent management
    // =========================================================================

    @Test
    fun subAgentIds_initiallyEmpty() {
        assertThat(manager.getSubAgentIds()).isEmpty()
    }

    @Test
    fun addSubAgent_registersAgent() {
        manager.addSubAgent("researcher")
        assertThat(manager.getSubAgentIds()).containsExactly("researcher")
    }

    @Test
    fun addMultipleSubAgents_preservesOrder() {
        manager.addSubAgent("researcher")
        manager.addSubAgent("coder")
        manager.addSubAgent("tester")
        assertThat(manager.getSubAgentIds())
            .containsExactly("researcher", "coder", "tester")
            .inOrder()
    }

    @Test
    fun addSubAgent_beyondMax_isIgnored() {
        manager.addSubAgent("agent1")
        manager.addSubAgent("agent2")
        manager.addSubAgent("agent3")
        manager.addSubAgent("agent4") // should be ignored (max 3)
        assertThat(manager.getSubAgentIds()).hasSize(3)
        assertThat(manager.getSubAgentIds()).doesNotContain("agent4")
    }

    @Test
    fun addSubAgent_duplicateId_isIgnored() {
        manager.addSubAgent("researcher")
        manager.addSubAgent("researcher") // duplicate
        assertThat(manager.getSubAgentIds()).containsExactly("researcher")
    }

    @Test
    fun removeSubAgent_removesAgent() {
        manager.addSubAgent("researcher")
        manager.addSubAgent("coder")
        manager.removeSubAgent("researcher")
        assertThat(manager.getSubAgentIds()).containsExactly("coder")
    }

    @Test
    fun removeSubAgent_nonexistent_noOp() {
        manager.addSubAgent("researcher")
        manager.removeSubAgent("nonexistent")
        assertThat(manager.getSubAgentIds()).containsExactly("researcher")
    }

    // =========================================================================
    // Sub-agent messages
    // =========================================================================

    @Test
    fun subAgentMessages_initiallyEmpty() {
        manager.addSubAgent("researcher")
        assertThat(manager.getSubAgentMessages("researcher")).isEmpty()
    }

    @Test
    fun subAgentMessages_unknownAgent_returnsEmpty() {
        assertThat(manager.getSubAgentMessages("unknown")).isEmpty()
    }

    @Test
    fun addSubAgentMessage_storesMessage() {
        manager.addSubAgent("researcher")
        val msg = ConversationMessage("researcher", "Found results", 1000L)
        manager.addSubAgentMessage("researcher", msg)
        assertThat(manager.getSubAgentMessages("researcher")).containsExactly(msg)
    }

    @Test
    fun addSubAgentMessage_unknownAgent_isIgnored() {
        val msg = ConversationMessage("unknown", "text", 1000L)
        manager.addSubAgentMessage("unknown", msg)
        assertThat(manager.getSubAgentMessages("unknown")).isEmpty()
    }

    @Test
    fun addMultipleSubAgentMessages_preservesOrder() {
        manager.addSubAgent("researcher")
        val msg1 = ConversationMessage("researcher", "First", 1000L)
        val msg2 = ConversationMessage("researcher", "Second", 2000L)
        manager.addSubAgentMessage("researcher", msg1)
        manager.addSubAgentMessage("researcher", msg2)
        assertThat(manager.getSubAgentMessages("researcher"))
            .containsExactly(msg1, msg2)
            .inOrder()
    }

    @Test
    fun removeSubAgent_clearsMessages() {
        manager.addSubAgent("researcher")
        manager.addSubAgentMessage(
            "researcher",
            ConversationMessage("researcher", "text", 1000L)
        )
        manager.removeSubAgent("researcher")
        assertThat(manager.getSubAgentMessages("researcher")).isEmpty()
    }

    // =========================================================================
    // Tab content IDs
    // =========================================================================

    @Test
    fun subAgentTabId_format() {
        assertThat(ConversationTabManager.subAgentTabId("researcher"))
            .isEqualTo("sub_agent_researcher")
    }

    @Test
    fun allTabIds_withNoSubAgents() {
        assertThat(manager.getAllConversationTabIds())
            .containsExactly(ConversationTabManager.LEAD_AGENT_TAB_ID)
    }

    @Test
    fun allTabIds_withSubAgents() {
        manager.addSubAgent("researcher")
        manager.addSubAgent("coder")
        assertThat(manager.getAllConversationTabIds())
            .containsExactly(
                ConversationTabManager.LEAD_AGENT_TAB_ID,
                "sub_agent_researcher",
                "sub_agent_coder"
            )
            .inOrder()
    }

    // =========================================================================
    // Active tab tracking
    // =========================================================================

    @Test
    fun activeTabId_defaultsToNull() {
        assertThat(manager.activeConversationTabId).isNull()
    }

    @Test
    fun setActiveTab_updatesActiveTabId() {
        manager.activeConversationTabId = ConversationTabManager.LEAD_AGENT_TAB_ID
        assertThat(manager.activeConversationTabId)
            .isEqualTo(ConversationTabManager.LEAD_AGENT_TAB_ID)
    }

    // =========================================================================
    // Mock data
    // =========================================================================

    @Test
    fun createWithMockData_hasLeadMessages() {
        val manager = ConversationTabManager.createWithMockData()
        assertThat(manager.getLeadAgentMessages()).isNotEmpty()
    }

    @Test
    fun createWithMockData_hasSubAgents() {
        val manager = ConversationTabManager.createWithMockData()
        assertThat(manager.getSubAgentIds()).isNotEmpty()
    }

    @Test
    fun createWithMockData_subAgentsHaveMessages() {
        val manager = ConversationTabManager.createWithMockData()
        for (agentId in manager.getSubAgentIds()) {
            assertThat(manager.getSubAgentMessages(agentId)).isNotEmpty()
        }
    }
}
