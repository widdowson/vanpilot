package com.vanpilot.auto.sync

import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.grpc.SyncServiceClient

/**
 * Polls the supervisor for events with adaptive batch sizing.
 *
 * Batch size grows when a full batch is returned (more events waiting),
 * shrinks on RPC errors (back-pressure / connection issues), and is
 * capped at [MAX_BATCH_SIZE].
 *
 * DisplayCommand events are only dispatched to [onDisplayCommand] when
 * the referenced bitmap is available in the cache. If the bitmap is
 * missing, a GetBitmap RPC is attempted first; if that also fails the
 * command is silently skipped (the next poll will retry).
 */
class SyncPoller(
    private val client: SyncServiceClient,
    private val processor: EventProcessor,
    private val cache: BitmapCache
) {
    var batchSize: Int = INITIAL_BATCH_SIZE
        private set

    var sinceTimestampMs: Long = 0
        private set

    /** Called when a DisplayCommand has a bitmap ready in the cache. */
    var onDisplayCommand: ((cacheKey: String) -> Unit)? = null

    /** Called for each TextMessage event received. */
    var onTextMessage: ((agentId: String, content: String) -> Unit)? = null

    /**
     * Performs one poll cycle: fetches events, processes them, and
     * dispatches callbacks. Returns the number of events received.
     */
    fun pollOnce(): Int {
        return try {
            val response = client.getEvents(sinceTimestampMs, batchSize)
            val events = response.eventsList

            processor.processEvents(events)

            if (events.isNotEmpty()) {
                sinceTimestampMs = events.last().timestampMs
            }

            // Dispatch text messages
            for (event in events) {
                if (event.hasTextMessage()) {
                    onTextMessage?.invoke(
                        event.textMessage.agentId,
                        event.textMessage.content
                    )
                }
            }

            // Handle display command if one was set
            val displayKey = processor.currentDisplayKey
            if (displayKey != null) {
                resolveAndDispatchDisplay(displayKey)
            }

            // Adaptive batching: grow when full batch returned
            if (events.size >= batchSize) {
                batchSize = minOf(batchSize * 2, MAX_BATCH_SIZE)
            }

            events.size
        } catch (_: Exception) {
            // Adaptive batching: shrink on error
            batchSize = maxOf(batchSize / 2, MIN_BATCH_SIZE)
            0
        }
    }

    /** Resets polling state (e.g. after reconnect). */
    fun resetSync() {
        sinceTimestampMs = 0
        batchSize = INITIAL_BATCH_SIZE
    }

    /**
     * Ensures the bitmap for [cacheKey] is in the cache before
     * dispatching onDisplayCommand. If the bitmap is missing, attempts
     * a GetBitmap RPC. If that fails, the display command is skipped.
     */
    private fun resolveAndDispatchDisplay(cacheKey: String) {
        if (!cache.contains(cacheKey)) {
            try {
                val resp = client.getBitmap(cacheKey)
                val bitmap = resp.bitmap
                if (bitmap.imageData.size() > 0) {
                    cache.put(bitmap.cacheKey, bitmap.imageData.toByteArray())
                }
            } catch (_: Exception) {
                // GetBitmap failed — skip display command
                return
            }
        }
        // Only dispatch if bitmap is now available
        if (cache.contains(cacheKey)) {
            onDisplayCommand?.invoke(cacheKey)
        }
    }

    companion object {
        const val INITIAL_BATCH_SIZE = 10
        const val MIN_BATCH_SIZE = 1
        const val MAX_BATCH_SIZE = 100
    }
}
