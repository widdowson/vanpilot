package com.vanpilot.phone

import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.R
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Robolectric tests for PhoneMainActivity.
 * Verifies activity lifecycle, tab layout, and fragment switching.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class PhoneMainActivityTest {

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
    fun activity_isCreated() {
        assertThat(activity).isNotNull()
    }

    @Test
    fun activity_hasFragmentContainer() {
        val container = activity.findViewById<FrameLayout>(R.id.fragment_container)
        assertThat(container).isNotNull()
    }

    @Test
    fun activity_hasTabBar() {
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        assertThat(tabBar).isNotNull()
    }

    @Test
    fun activity_hasVisualTab() {
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        val visualTab = findTabByText(tabBar, "Visual")
        assertThat(visualTab).isNotNull()
    }

    @Test
    fun activity_hasLeadAgentTab() {
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        val leadTab = findTabByText(tabBar, "Lead Agent")
        assertThat(leadTab).isNotNull()
    }

    @Suppress("DEPRECATION")
    @Test
    fun activity_defaultFragmentIsVisualCard() {
        activity.fragmentManager.executePendingTransactions()
        val fragment = activity.fragmentManager
            .findFragmentById(R.id.fragment_container)
        assertThat(fragment).isInstanceOf(VisualCardFragment::class.java)
    }

    @Suppress("DEPRECATION")
    @Test
    fun activity_selectLeadAgentTab_showsConversationFragment() {
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        val leadTab = findTabByText(tabBar, "Lead Agent")!!
        leadTab.performClick()
        activity.fragmentManager.executePendingTransactions()

        val fragment = activity.fragmentManager
            .findFragmentById(R.id.fragment_container)
        assertThat(fragment).isInstanceOf(ConversationFragment::class.java)
    }

    @Suppress("DEPRECATION")
    @Test
    fun activity_selectVisualTab_showsVisualCardFragment() {
        // First switch to Lead Agent
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        findTabByText(tabBar, "Lead Agent")!!.performClick()
        activity.fragmentManager.executePendingTransactions()

        // Then switch back to Visual
        findTabByText(tabBar, "Visual")!!.performClick()
        activity.fragmentManager.executePendingTransactions()

        val fragment = activity.fragmentManager
            .findFragmentById(R.id.fragment_container)
        assertThat(fragment).isInstanceOf(VisualCardFragment::class.java)
    }

    @Test
    fun tabManager_isAccessible() {
        assertThat(activity.tabManager).isNotNull()
    }

    private fun findTabByText(tabBar: LinearLayout, text: String): Button? {
        for (i in 0 until tabBar.childCount) {
            val child = tabBar.getChildAt(i)
            if (child is Button && child.text == text) {
                return child
            }
        }
        return null
    }
}
