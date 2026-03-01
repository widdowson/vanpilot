package com.vanpilot.auto

/**
 * A single text message in a conversation feed.
 * Used to display agent output in ListTemplate rows.
 *
 * @property sender Identifier of the agent that produced this message.
 * @property text The message content.
 * @property timestampMs Unix timestamp in milliseconds when the message was produced.
 */
data class ConversationMessage(
    val sender: String,
    val text: String,
    val timestampMs: Long
)
