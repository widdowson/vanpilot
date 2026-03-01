package com.vanpilot.auto.connectivity

import com.vanpilot.auto.grpc.SyncServiceClient
import com.vanpilot.auto.sync.EventProcessor
import io.grpc.ManagedChannel
import io.grpc.StatusRuntimeException

/**
 * Orchestrates gRPC polling with connection-aware adaptive batching.
 *
 * AC-9.1: Detects loss of connectivity.
 * AC-9.4: On reconnection, sync resumes from the last known timestamp using GetEvents.
 * AC-9.5: Adaptive batching starts conservatively on reconnection and increases.
 */
class SyncManager(
    channel: ManagedChannel,
    private val eventProcessor: EventProcessor
) {
    private val client = SyncServiceClient(channel)
    private val monitor = ConnectionMonitor()
    private val batchConfig = AdaptiveBatchConfig()

    private var sinceTimestampMs: Long = 0

    val connectionState: ConnectionState
        get() = monitor.state

    fun addConnectionListener(listener: (ConnectionState) -> Unit) {
        monitor.addListener(listener)
    }

    fun poll() {
        try {
            val response = client.getEvents(sinceTimestampMs, batchConfig.maxCount)

            val wasDisconnected = monitor.state != ConnectionState.CONNECTED
            monitor.onRpcSuccess()

            if (wasDisconnected) {
                batchConfig.onReconnected()
            } else {
                batchConfig.onSuccessfulPoll()
            }

            val events = response.eventsList
            eventProcessor.processEvents(events)

            if (events.isNotEmpty()) {
                sinceTimestampMs = events.last().timestampMs
            }
        } catch (e: StatusRuntimeException) {
            monitor.onRpcFailure()
            batchConfig.onPollFailure()
        }
    }

    fun shutdown() {
        client.shutdown()
    }
}
