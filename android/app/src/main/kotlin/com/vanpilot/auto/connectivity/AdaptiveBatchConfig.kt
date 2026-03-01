package com.vanpilot.auto.connectivity

/**
 * Manages adaptive batching of max_count for GetEvents requests.
 *
 * AC-9.5: Adaptive batching starts conservatively on reconnection and increases.
 *
 * From DESIGN.md:
 * - Stable connection (no recent disconnects): max_count = 50
 * - Just reconnected: max_count = 5, increasing gradually as successful responses are received.
 */
class AdaptiveBatchConfig(
    private val stableMaxCount: Int = 50,
    private val conservativeMaxCount: Int = 5,
    private val maxUpperBound: Int = 200
) {
    var maxCount: Int = stableMaxCount
        private set

    private var successCountSinceReset: Int = 0

    fun onReconnected() {
        maxCount = conservativeMaxCount
        successCountSinceReset = 0
    }

    fun onSuccessfulPoll() {
        successCountSinceReset++
        if (maxCount < stableMaxCount) {
            maxCount = (maxCount * 2).coerceAtMost(stableMaxCount)
        }
        maxCount = maxCount.coerceAtMost(maxUpperBound)
    }

    fun onPollFailure() {
        maxCount = conservativeMaxCount
        successCountSinceReset = 0
    }
}
