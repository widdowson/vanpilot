package com.vanpilot.auto

import com.vanpilot.auto.cache.BitmapCache
import com.vanpilot.auto.connectivity.ConnectionState
import com.vanpilot.auto.connectivity.SyncManager
import com.vanpilot.auto.sync.EventProcessor
import io.grpc.ManagedChannel
import java.io.Closeable

/**
 * Bridges gRPC event polling to the Android Auto UI.
 *
 * Routes text messages from the supervisor to the ConversationTabManager:
 * - "lead" agent messages go to the lead agent tab
 * - All other agent IDs create/update sub-agent tabs
 *
 * Calls [onUpdate] after each text message so the screen can invalidate.
 */
class GrpcPollLoop(
    channel: ManagedChannel,
    private val tabManager: ConversationTabManager,
    bitmapCache: BitmapCache,
    private val onUpdate: () -> Unit
) : Closeable {

    private val eventProcessor = EventProcessor(bitmapCache, fetchEnabled = true).apply {
        textMessageListener = { agentId, content, timestampMs ->
            routeTextMessage(agentId, content, timestampMs)
        }
    }

    private val syncManager = SyncManager(channel, eventProcessor)

    val connectionState: ConnectionState
        get() = syncManager.connectionState

    fun addConnectionListener(listener: (ConnectionState) -> Unit) {
        syncManager.addConnectionListener(listener)
    }

    fun poll() {
        syncManager.poll()
    }

    fun shutdown() {
        syncManager.shutdown()
    }

    override fun close() {
        shutdown()
    }

    private fun routeTextMessage(agentId: String, content: String, timestampMs: Long) {
        val message = ConversationMessage(agentId, content, timestampMs)
        if (agentId == "lead") {
            tabManager.addLeadAgentMessage(message)
        } else {
            tabManager.addSubAgent(agentId)
            tabManager.addSubAgentMessage(agentId, message)
        }
        onUpdate()
    }
}
