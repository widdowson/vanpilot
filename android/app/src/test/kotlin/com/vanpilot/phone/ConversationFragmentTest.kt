package com.vanpilot.phone

import android.widget.LinearLayout
import android.widget.TextView
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
 * Robolectric tests for ConversationFragment.
 * Verifies message display and title rendering.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class ConversationFragmentTest {

    private lateinit var activity: PhoneMainActivity

    @Before
    fun setUp() {
        activity = Robolectric.buildActivity(PhoneMainActivity::class.java)
            .create()
            .start()
            .resume()
            .get()
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_isCreated() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        assertThat(fragment).isNotNull()
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_showsTitle() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val titleView = fragment.view!!.findViewById<TextView>(R.id.conversation_title)
        assertThat(titleView.text.toString()).isEqualTo("Lead Agent")
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_showsMessages() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        // Mock data has 3 lead agent messages
        assertThat(container.childCount).isEqualTo(3)
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_messageContainsText() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        // First message from mock data
        val firstMessage = container.getChildAt(0) as LinearLayout
        val textView = firstMessage.getChildAt(1) as TextView
        assertThat(textView.text.toString()).isEqualTo("Starting analysis of the codebase...")
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_messageContainsSender() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        val firstMessage = container.getChildAt(0) as LinearLayout
        val senderView = firstMessage.getChildAt(0) as TextView
        assertThat(senderView.text.toString()).isEqualTo("lead")
    }

    @Suppress("DEPRECATION")
    @Test
    fun fragment_noMessages_showsPlaceholder() {
        val fragment = ConversationFragment.newInstance("Test Agent", emptyList())
        activity.fragmentManager.beginTransaction()
            .replace(R.id.fragment_container, fragment)
            .commit()
        // Execute pending transactions
        activity.fragmentManager.executePendingTransactions()

        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        assertThat(container.childCount).isEqualTo(1)
        val placeholder = container.getChildAt(0) as TextView
        assertThat(placeholder.text.toString()).isEqualTo("No messages yet")
    }

    private fun switchToLeadAgent() {
        val tabBar = activity.findViewById<LinearLayout>(R.id.tab_bar)
        for (i in 0 until tabBar.childCount) {
            val child = tabBar.getChildAt(i)
            if (child is android.widget.Button && child.text == "Lead Agent") {
                child.performClick()
                return
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun getConversationFragment(): ConversationFragment {
        // Need to execute pending transactions since we use commit() not commitNow()
        activity.fragmentManager.executePendingTransactions()
        return activity.fragmentManager
            .findFragmentById(R.id.fragment_container) as ConversationFragment
    }
}
