package com.vanpilot.phone

import android.widget.LinearLayout
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textview.MaterialTextView
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
class ConversationFragmentMaterialTest {

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
    fun messages_useCardView() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        // Each message should be wrapped in a MaterialCardView
        for (i in 0 until container.childCount) {
            assertThat(container.getChildAt(i)).isInstanceOf(MaterialCardView::class.java)
        }
    }

    @Test
    fun messageCard_hasSenderText() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        val firstCard = container.getChildAt(0) as MaterialCardView
        // Card has a LinearLayout with sender + text
        val cardContent = firstCard.getChildAt(0) as LinearLayout
        val senderView = cardContent.getChildAt(0) as MaterialTextView
        assertThat(senderView.text.toString()).isEqualTo("lead")
    }

    @Test
    fun messageCard_hasMessageText() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val container = fragment.view!!.findViewById<LinearLayout>(R.id.message_container)
        val firstCard = container.getChildAt(0) as MaterialCardView
        val cardContent = firstCard.getChildAt(0) as LinearLayout
        val textView = cardContent.getChildAt(1) as MaterialTextView
        assertThat(textView.text.toString()).isEqualTo("Starting analysis of the codebase...")
    }

    @Test
    fun conversationTitle_usesMaterialTextView() {
        switchToLeadAgent()
        val fragment = getConversationFragment()
        val titleView = fragment.view!!.findViewById<MaterialTextView>(R.id.conversation_title)
        assertThat(titleView).isNotNull()
        assertThat(titleView.text.toString()).isEqualTo("Lead Agent")
    }

    private fun switchToLeadAgent() {
        val tabLayout = activity.findViewById<com.google.android.material.tabs.TabLayout>(R.id.tab_layout)
        tabLayout.getTabAt(1)?.select()
    }

    private fun getConversationFragment(): ConversationFragment {
        activity.supportFragmentManager.executePendingTransactions()
        return activity.supportFragmentManager
            .findFragmentById(R.id.fragment_container) as ConversationFragment
    }
}
