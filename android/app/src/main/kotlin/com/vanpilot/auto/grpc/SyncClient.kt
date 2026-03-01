package com.vanpilot.auto.grpc

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import com.vanpilot.auto.BitmapCache
import com.vanpilot.proto.v1.Event
import com.vanpilot.proto.v1.GetBitmapRequest
import com.vanpilot.proto.v1.GetEventsRequest
import com.vanpilot.proto.v1.SyncServiceGrpc
import io.grpc.ManagedChannel
import io.grpc.StatusRuntimeException

/**
 * gRPC client that polls the supervisor's SyncService for events.
 *
 * Handles three event types:
 * - BitmapPayload: decode PNG bytes and store in BitmapCache
 * - DisplayCommand: look up cached bitmap, fallback to GetBitmap RPC
 * - TextMessage: forward to callback
 *
 * Uses adaptive batching: max_count starts at [DEFAULT_MAX_COUNT],
 * drops to [RECONNECT_MAX_COUNT] on error, doubles on success up to cap.
 */
class SyncClient(
    private val channel: ManagedChannel,
    private val bitmapCache: BitmapCache,
    private val onDisplayCommand: (String) -> Unit,
    private val onTextMessage: (String, String) -> Unit = { _, _ -> },
) {
    companion object {
        const val TAG = "SyncClient"
        const val DEFAULT_MAX_COUNT = 50
        const val RECONNECT_MAX_COUNT = 5
        const val MAX_BATCH_SIZE = 200
    }

    private val stub: SyncServiceGrpc.SyncServiceBlockingStub =
        SyncServiceGrpc.newBlockingStub(channel)

    var sinceTimestampMs: Long = 0
        private set

    var maxCount: Int = DEFAULT_MAX_COUNT
        private set

    /**
     * Poll for new events. Returns the list of events received.
     * Updates sinceTimestampMs for the next poll.
     */
    fun pollEvents(): List<Event> {
        return try {
            val request = GetEventsRequest.newBuilder()
                .setSinceTimestampMs(sinceTimestampMs)
                .setMaxCount(maxCount)
                .build()
            val response = stub.getEvents(request)
            val events = response.eventsList

            if (events.isNotEmpty()) {
                sinceTimestampMs = events.last().timestampMs + 1
                // Adaptive batching: grow on success
                if (maxCount < MAX_BATCH_SIZE) {
                    maxCount = (maxCount * 2).coerceAtMost(MAX_BATCH_SIZE)
                }
            }

            events.forEach { handleEvent(it) }
            events
        } catch (e: StatusRuntimeException) {
            Log.w(TAG, "gRPC error polling events: ${e.status}", e)
            // Adaptive batching: shrink on error
            maxCount = RECONNECT_MAX_COUNT
            emptyList()
        }
    }

    /**
     * Request a specific bitmap from the supervisor via GetBitmap RPC.
     * Returns the decoded Bitmap or null if not found.
     */
    fun requestBitmap(cacheKey: String): Bitmap? {
        return try {
            val request = GetBitmapRequest.newBuilder()
                .setCacheKey(cacheKey)
                .build()
            val response = stub.getBitmap(request)
            if (response.hasBitmap()) {
                val bytes = response.bitmap.imageData.toByteArray()
                val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                if (bitmap != null) {
                    bitmapCache.put(cacheKey, bitmap)
                }
                bitmap
            } else {
                null
            }
        } catch (e: StatusRuntimeException) {
            Log.w(TAG, "gRPC error requesting bitmap $cacheKey: ${e.status}", e)
            null
        }
    }

    /**
     * Reset sync state (e.g., after reconnection).
     */
    fun resetSync() {
        sinceTimestampMs = 0
        maxCount = RECONNECT_MAX_COUNT
    }

    private fun handleEvent(event: Event) {
        when (event.payloadCase) {
            Event.PayloadCase.BITMAP_PAYLOAD -> {
                val payload = event.bitmapPayload
                val bytes = payload.imageData.toByteArray()
                val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                if (bitmap != null) {
                    bitmapCache.put(payload.cacheKey, bitmap)
                    Log.d(TAG, "Cached bitmap ${payload.cacheKey}")
                } else {
                    Log.w(TAG, "Failed to decode bitmap ${payload.cacheKey}")
                }
            }
            Event.PayloadCase.DISPLAY_COMMAND -> {
                val cacheKey = event.displayCommand.cacheKey
                if (!bitmapCache.has(cacheKey)) {
                    // Fallback: request bitmap from supervisor
                    requestBitmap(cacheKey)
                }
                onDisplayCommand(cacheKey)
            }
            Event.PayloadCase.TEXT_MESSAGE -> {
                val msg = event.textMessage
                onTextMessage(msg.agentId, msg.content)
            }
            else -> {
                Log.d(TAG, "Unhandled event type: ${event.payloadCase}")
            }
        }
    }
}
