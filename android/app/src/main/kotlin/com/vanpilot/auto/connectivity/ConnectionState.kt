package com.vanpilot.auto.connectivity

/**
 * Represents the connection state between the Android app and the Mac Studio supervisor.
 *
 * AC-9.1: The app detects loss of connectivity to the Mac Studio.
 * AC-9.2: In offline mode: voice input is disabled, last bitmap is retained,
 *          disconnect indicator is visible in the tab bar.
 */
enum class ConnectionState(
    val isOnline: Boolean,
    val voiceInputEnabled: Boolean,
    val showDisconnectIndicator: Boolean
) {
    CONNECTED(
        isOnline = true,
        voiceInputEnabled = true,
        showDisconnectIndicator = false
    ),
    DISCONNECTED(
        isOnline = false,
        voiceInputEnabled = false,
        showDisconnectIndicator = true
    ),
    RECONNECTING(
        isOnline = false,
        voiceInputEnabled = false,
        showDisconnectIndicator = true
    )
}
