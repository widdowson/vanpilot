package com.vanpilot.phone

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import com.vanpilot.auto.ConversationTabManager
import com.vanpilot.auto.R

/**
 * Main activity for the VanPilot phone UI.
 *
 * Mirrors the Android Auto TabTemplate layout:
 * - Visual Card tab: displays the latest bitmap from the MCP server
 * - Lead Agent tab: conversation feed from the lead agent
 * - Sub-Agent tabs: conversation feeds for active sub-agents (up to 2)
 *
 * Uses AndroidX FragmentActivity and Fragment for lifecycle-safe fragment management.
 */
class PhoneMainActivity : FragmentActivity() {

    val tabManager = ConversationTabManager.createWithMockData()

    private var activeTabId: String = VISUAL_TAB_ID
    private val tabButtons = mutableListOf<Button>()

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
        const val LEAD_AGENT_TAB_ID = ConversationTabManager.LEAD_AGENT_TAB_ID
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_phone_main)

        buildTabs()
        if (savedInstanceState == null) {
            showFragment(VISUAL_TAB_ID)
        }
    }

    private fun buildTabs() {
        val tabBar = findViewById<LinearLayout>(R.id.tab_bar)
        tabBar.removeAllViews()
        tabButtons.clear()

        addTab(tabBar, "Visual", VISUAL_TAB_ID)
        addTab(tabBar, "Lead Agent", LEAD_AGENT_TAB_ID)

        for ((index, agentId) in tabManager.getSubAgentIds().withIndex()) {
            if (index >= ConversationTabManager.MAX_SUB_AGENT_TABS) break
            val tabId = ConversationTabManager.subAgentTabId(agentId)
            addTab(tabBar, agentId.replaceFirstChar { it.uppercase() }, tabId)
        }

        updateTabHighlight()
    }

    private fun addTab(tabBar: LinearLayout, title: String, tabId: String) {
        val button = Button(this).apply {
            text = title
            tag = tabId
            setOnClickListener { selectTab(tabId) }
            val params = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            params.setMargins(4, 4, 4, 4)
            layoutParams = params
        }
        tabBar.addView(button)
        tabButtons.add(button)
    }

    fun selectTab(tabId: String) {
        activeTabId = tabId
        updateTabHighlight()
        showFragment(tabId)
    }

    private fun updateTabHighlight() {
        for (button in tabButtons) {
            if (button.tag == activeTabId) {
                button.setTypeface(null, Typeface.BOLD)
                button.setBackgroundColor(Color.parseColor("#1A8A7D"))
                button.setTextColor(Color.WHITE)
            } else {
                button.setTypeface(null, Typeface.NORMAL)
                button.setBackgroundColor(Color.LTGRAY)
                button.setTextColor(Color.BLACK)
            }
        }
    }

    private fun showFragment(tabId: String) {
        val fragment: Fragment = when (tabId) {
            VISUAL_TAB_ID -> VisualCardFragment()
            LEAD_AGENT_TAB_ID -> ConversationFragment.newInstance(
                "Lead Agent",
                tabManager.getLeadAgentMessages()
            )
            else -> {
                val agentId = ConversationTabManager.agentIdFromTabId(tabId)
                ConversationFragment.newInstance(
                    agentId,
                    tabManager.getSubAgentMessages(agentId)
                )
            }
        }

        supportFragmentManager.beginTransaction()
            .replace(R.id.fragment_container, fragment)
            .commit()
    }
}
