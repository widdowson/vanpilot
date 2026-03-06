package com.vanpilot.phone

import androidx.fragment.app.Fragment
import android.graphics.Typeface
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import com.vanpilot.auto.ConversationMessage
import com.vanpilot.auto.R

/**
 * Fragment that displays a conversation feed for an agent.
 *
 * Replaces the Android Auto ListTemplate rows with standard Android
 * TextViews in a ScrollView. Each message shows the sender and text.
 */
class ConversationFragment : Fragment() {

    companion object {
        private const val ARG_TITLE = "title"
        private const val ARG_MSG_SENDERS = "msg_senders"
        private const val ARG_MSG_TEXTS = "msg_texts"
        private const val ARG_MSG_TIMESTAMPS = "msg_timestamps"

        fun newInstance(
            title: String,
            messages: List<ConversationMessage>
        ): ConversationFragment {
            return ConversationFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_TITLE, title)
                    putStringArray(ARG_MSG_SENDERS, messages.map { it.sender }.toTypedArray())
                    putStringArray(ARG_MSG_TEXTS, messages.map { it.text }.toTypedArray())
                    putLongArray(ARG_MSG_TIMESTAMPS, messages.map { it.timestampMs }.toLongArray())
                }
            }
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.fragment_conversation, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val args = arguments ?: return
        val title = args.getString(ARG_TITLE, "")
        val senders = args.getStringArray(ARG_MSG_SENDERS) ?: emptyArray()
        val texts = args.getStringArray(ARG_MSG_TEXTS) ?: emptyArray()

        val titleView = view.findViewById<TextView>(R.id.conversation_title)
        titleView.text = title

        val container = view.findViewById<LinearLayout>(R.id.message_container)
        container.removeAllViews()

        if (senders.isEmpty()) {
            val placeholder = TextView(requireActivity()).apply {
                text = "No messages yet"
                setPadding(16, 16, 16, 16)
            }
            container.addView(placeholder)
        } else {
            for (i in senders.indices) {
                val messageView = buildMessageView(senders[i], texts[i])
                container.addView(messageView)
            }
        }
    }

    private fun buildMessageView(sender: String, text: String): LinearLayout {
        return LinearLayout(requireActivity()).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(8, 8, 8, 8)

            val senderView = TextView(context).apply {
                this.text = sender
                setTypeface(null, Typeface.BOLD)
                textSize = 12f
            }
            addView(senderView)

            val textView = TextView(context).apply {
                this.text = text
                textSize = 14f
            }
            addView(textView)
        }
    }
}
