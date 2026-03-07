package com.vanpilot.phone

import android.widget.Toolbar
import com.google.android.material.tabs.TabLayout
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.R
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class PhoneMainActivityMaterialTest {

    private lateinit var activity: PhoneMainActivity

    @Before
    fun setUp() {
        activity = Robolectric.buildActivity(PhoneMainActivity::class.java)
            .create()
            .start()
            .resume()
            .get()
    }

    @Test
    fun activity_hasToolbar() {
        val toolbar = activity.findViewById<Toolbar>(R.id.toolbar)
        assertThat(toolbar).isNotNull()
    }

    @Test
    fun toolbar_showsAppName() {
        val toolbar = activity.findViewById<Toolbar>(R.id.toolbar)
        assertThat(toolbar.title.toString()).isEqualTo("VanPilot")
    }

    @Test
    fun activity_hasTabLayout() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        assertThat(tabLayout).isNotNull()
    }

    @Test
    fun tabLayout_hasVisualTab() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        val tabTexts = (0 until tabLayout.tabCount).map { tabLayout.getTabAt(it)?.text.toString() }
        assertThat(tabTexts).contains("Visual")
    }

    @Test
    fun tabLayout_hasLeadAgentTab() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        val tabTexts = (0 until tabLayout.tabCount).map { tabLayout.getTabAt(it)?.text.toString() }
        assertThat(tabTexts).contains("Lead Agent")
    }

    @Test
    fun tabLayout_defaultSelectionIsVisualTab() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        assertThat(tabLayout.getTabAt(0)?.text.toString()).isEqualTo("Visual")
        assertThat(tabLayout.selectedTabPosition).isEqualTo(0)
    }

    @Test
    fun tabLayout_selectLeadAgent_showsConversationFragment() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        tabLayout.getTabAt(1)?.select()
        activity.supportFragmentManager.executePendingTransactions()

        val fragment = activity.supportFragmentManager
            .findFragmentById(R.id.fragment_container)
        assertThat(fragment).isInstanceOf(ConversationFragment::class.java)
    }

    @Test
    fun toolbar_hasSubtitleForConnectionStatus() {
        val toolbar = activity.findViewById<Toolbar>(R.id.toolbar)
        assertThat(toolbar.subtitle).isNotNull()
    }
}
