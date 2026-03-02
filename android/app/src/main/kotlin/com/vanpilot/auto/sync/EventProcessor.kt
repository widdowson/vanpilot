package com.vanpilot.auto.sync

import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.cache.BitmapFetcher
import com.vanpilot.proto.v1.Event
import java.util.logging.Logger

/**
 * Processes Event objects received from GetEventsResponse.
 *
 * Stores processed results internally for consumption by the UI layer.
 * When a DisplayCommand references a cache key not in BitmapCache and
 * a [BitmapFetcher] is configured, automatically requests the missing
 * bitmap from the supervisor (AC-7.2).
 */
class EventProcessor(
    private val cache: BitmapCache,
    private val fetcher: BitmapFetcher? = null
) {

    private val logger = Logger.getLogger(EventProcessor::class.java.name)

    private val _textMessages = mutableListOf<ProcessedTextMessage>()
    val textMessages: List<ProcessedTextMessage> get() = _textMessages.toList()

    private val _alerts = mutableListOf<ProcessedAlert>()
    val alerts: List<ProcessedAlert> get() = _alerts.toList()

    var currentDisplayKey: String? = null
        private set

    /** Count of auto-fetched bitmaps (for testing). */
    var fetchCount: Int = 0
        private set

    /** Count of unknown/unhandled event types (for testing). */
    var unknownEventCount: Int = 0
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
                val key = event.displayCommand.cacheKey
                // Auto-request missing bitmap from supervisor (AC-7.2)
                // TODO: fetchBitmap is synchronous — should be async for large bitmaps
                //  to avoid blocking the event processing loop.
                if (!cache.contains(key) && fetcher != null) {
                    val data = fetcher.fetchBitmap(key)
                    if (data != null) {
                        cache.put(key, data)
                        fetchCount++
                    }
                }
                currentDisplayKey = key
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
            else -> {
                unknownEventCount++
                logger.warning("Unknown event type at timestampMs=${event.timestampMs}")
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
