package com.vanpilot.auto.connectivity

/**
 * Monitors gRPC connectivity and tracks connection state transitions.
 *
 * AC-9.1: The app detects loss of connectivity to the Mac Studio.
 *
 * Thread-safe: all state mutations are synchronized.
 */
class ConnectionMonitor {

    private val lock = Any()
    private val listeners = mutableListOf<(ConnectionState) -> Unit>()

    var state: ConnectionState = ConnectionState.DISCONNECTED
        private set

    var consecutiveFailures: Int = 0
        private set

    /** Exposed for the UI layer to show reconnection status (e.g. briefly flash an indicator). */
    var wasRecentlyReconnected: Boolean = false
        private set

    fun addListener(listener: (ConnectionState) -> Unit) {
        synchronized(lock) {
            listeners.add(listener)
        }
    }

    fun removeListener(listener: (ConnectionState) -> Unit) {
        synchronized(lock) {
            listeners.remove(listener)
        }
    }

    fun onRpcSuccess() {
        synchronized(lock) {
            if (state == ConnectionState.RECONNECTING || state == ConnectionState.DISCONNECTED) {
                wasRecentlyReconnected = state != ConnectionState.DISCONNECTED || consecutiveFailures > 0
            }
            consecutiveFailures = 0
            transition(ConnectionState.CONNECTED)
        }
    }

    fun onRpcFailure() {
        synchronized(lock) {
            consecutiveFailures++
            transition(ConnectionState.DISCONNECTED)
        }
    }

    fun onReconnectAttempt() {
        synchronized(lock) {
            transition(ConnectionState.RECONNECTING)
        }
    }

    /** Called by the UI layer after it has consumed the reconnection signal. */
    fun clearRecentReconnection() {
        synchronized(lock) {
            wasRecentlyReconnected = false
        }
    }

    private fun transition(newState: ConnectionState) {
        if (state == newState) return
        state = newState
        val listenersCopy = listeners.toList()
        for (listener in listenersCopy) {
            listener(newState)
        }
    }
}
