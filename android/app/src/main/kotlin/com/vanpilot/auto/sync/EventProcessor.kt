package com.vanpilot.auto.sync

import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.proto.v1.Event

/**
 * Processes Event objects received from GetEventsResponse.
 *
 * Stores processed results internally for consumption by the UI layer.
 */
class EventProcessor(private val cache: BitmapCache) {

    private val _textMessages = mutableListOf<ProcessedTextMessage>()
    val textMessages: List<ProcessedTextMessage> get() = _textMessages.toList()

    private val _alerts = mutableListOf<ProcessedAlert>()
    val alerts: List<ProcessedAlert> get() = _alerts.toList()

    var currentDisplayKey: String? = null
        private set

    fun processEvent(event: Event) {
        when {
            event.hasTextMessage() -> {
                val msg = event.textMessage
                _textMessages.add(
                    ProcessedTextMessage(msg.agentId, msg.content, event.timestampMs)
                )
            }
            event.hasBitmapPayload() -> {
                val payload = event.bitmapPayload
                cache.put(payload.cacheKey, payload.imageData.toByteArray())
            }
            event.hasDisplayCommand() -> {
                currentDisplayKey = event.displayCommand.cacheKey
            }
            event.hasWatchdogTimeout() -> {
                val wt = event.watchdogTimeout
                _alerts.add(
                    ProcessedAlert(
                        AlertType.WATCHDOG_TIMEOUT,
                        "Agent ${wt.agentId} unresponsive for ${wt.silentDurationMs}ms",
                        event.timestampMs
                    )
                )
            }
            event.hasInputDeliveryFailure() -> {
                val failure = event.inputDeliveryFailure
                _alerts.add(
                    ProcessedAlert(
                        AlertType.INPUT_DELIVERY_FAILURE,
                        "Failed to deliver '${failure.attemptedInput}' to ${failure.targetAgentId}",
                        event.timestampMs
                    )
                )
            }
        }
    }

    fun processEvents(events: List<Event>) {
        events.forEach { processEvent(it) }
    }
}

data class ProcessedTextMessage(
    val agentId: String,
    val content: String,
    val timestampMs: Long
)

data class ProcessedAlert(
    val type: AlertType,
    val message: String,
    val timestampMs: Long
)

enum class AlertType {
    WATCHDOG_TIMEOUT,
    INPUT_DELIVERY_FAILURE
}
