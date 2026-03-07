package com.vanpilot.phone

import android.graphics.Color
import android.os.Bundle
import android.widget.Toolbar
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import com.google.android.material.tabs.TabLayout
import com.vanpilot.auto.ConversationTabManager
import com.vanpilot.auto.R

class PhoneMainActivity : FragmentActivity() {

    val tabManager = ConversationTabManager.createWithMockData()

    companion object {
        const val VISUAL_TAB_ID = "visual_card"
        const val LEAD_AGENT_TAB_ID = ConversationTabManager.LEAD_AGENT_TAB_ID
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        setTheme(com.google.android.material.R.style.Theme_MaterialComponents_Light_NoActionBar)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_phone_main)

        setupToolbar()
        setupTabs()

        if (savedInstanceState == null) {
            showFragment(VISUAL_TAB_ID)
        }
    }

    private fun setupToolbar() {
        val toolbar = findViewById<Toolbar>(R.id.toolbar)
        toolbar.title = getString(R.string.app_name)
        toolbar.subtitle = "Disconnected"
    }

    private fun setupTabs() {
        val tabLayout = findViewById<TabLayout>(R.id.tab_layout)
        val primaryColor = ContextCompat.getColor(this, R.color.md_theme_primary)
        tabLayout.setSelectedTabIndicatorColor(primaryColor)
        tabLayout.setTabTextColors(Color.GRAY, primaryColor)
        tabLayout.tabMode = TabLayout.MODE_SCROLLABLE

        tabLayout.addTab(tabLayout.newTab().setText("Visual").setTag(VISUAL_TAB_ID))
        tabLayout.addTab(tabLayout.newTab().setText("Lead Agent").setTag(LEAD_AGENT_TAB_ID))

        for ((index, agentId) in tabManager.getSubAgentIds().withIndex()) {
            if (index >= ConversationTabManager.MAX_SUB_AGENT_TABS) break
            val tabId = ConversationTabManager.subAgentTabId(agentId)
            tabLayout.addTab(
                tabLayout.newTab()
                    .setText(agentId.replaceFirstChar { it.uppercase() })
                    .setTag(tabId)
            )
        }

        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                val tabId = tab.tag as String
                showFragment(tabId)
            }
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })
    }

    fun selectTab(tabId: String) {
        val tabLayout = findViewById<TabLayout>(R.id.tab_layout)
        for (i in 0 until tabLayout.tabCount) {
            val tab = tabLayout.getTabAt(i)
            if (tab?.tag == tabId) {
                tab.select()
                return
            }
        }
    }

    fun updateConnectionStatus(connected: Boolean) {
        val toolbar = findViewById<Toolbar>(R.id.toolbar)
        toolbar.subtitle = if (connected) "Connected" else "Disconnected"
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
