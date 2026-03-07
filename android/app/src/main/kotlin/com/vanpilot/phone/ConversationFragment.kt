package com.vanpilot.phone

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textview.MaterialTextView
import com.vanpilot.auto.ConversationMessage
import com.vanpilot.auto.R

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

        val titleView = view.findViewById<MaterialTextView>(R.id.conversation_title)
        titleView.text = title

        val container = view.findViewById<LinearLayout>(R.id.message_container)
        container.removeAllViews()

        if (senders.isEmpty()) {
            val placeholder = MaterialTextView(requireActivity()).apply {
                text = "No messages yet"
                setPadding(16, 16, 16, 16)
                setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyMedium)
            }
            container.addView(placeholder)
        } else {
            for (i in senders.indices) {
                val messageView = buildMessageView(senders[i], texts[i])
                container.addView(messageView)
            }
        }
    }

    private fun buildMessageView(sender: String, text: String): MaterialCardView {
        return MaterialCardView(requireActivity()).apply {
            val params = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            params.setMargins(8, 4, 8, 4)
            layoutParams = params
            radius = 12f
            cardElevation = 2f

            val content = LinearLayout(context).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(16, 12, 16, 12)

                val senderView = MaterialTextView(context).apply {
                    this.text = sender
                    setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_LabelMedium)
                }
                addView(senderView)

                val textView = MaterialTextView(context).apply {
                    this.text = text
                    setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyMedium)
                }
                addView(textView)
            }
            addView(content)
        }
    }
}
