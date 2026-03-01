package com.vanpilot.auto.connectivity

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Tests for AdaptiveBatchConfig - adjusts max_count based on connection health.
 *
 * AC-9.5: Adaptive batching starts conservatively on reconnection and increases.
 *
 * From DESIGN.md:
 * - Stable connection (no recent disconnects): max_count = 50
 * - Just reconnected: max_count = 5, increasing gradually
 */
@RunWith(JUnit4::class)
class AdaptiveBatchConfigTest {

    private lateinit var config: AdaptiveBatchConfig

    @Before
    fun setUp() {
        config = AdaptiveBatchConfig()
    }

    @Test
    fun defaultMaxCount_is50() {
        assertThat(config.maxCount).isEqualTo(50)
    }

    @Test
    fun afterReconnection_maxCountResetsToConservative() {
        // AC-9.5: starts conservatively on reconnection
        config.onReconnected()
        assertThat(config.maxCount).isEqualTo(5)
    }

    @Test
    fun afterSuccessfulPoll_maxCountIncreases() {
        config.onReconnected()
        assertThat(config.maxCount).isEqualTo(5)

        config.onSuccessfulPoll()
        assertThat(config.maxCount).isGreaterThan(5)
    }

    @Test
    fun gradualIncrease_reachesStableMaxCount() {
        config.onReconnected()

        // Simulate multiple successful polls
        repeat(20) { config.onSuccessfulPoll() }

        // Should reach stable max_count of 50
        assertThat(config.maxCount).isEqualTo(50)
    }

    @Test
    fun maxCountNeverExceeds200() {
        // Even with many successful polls, don't go above 200
        repeat(100) { config.onSuccessfulPoll() }
        assertThat(config.maxCount).isAtMost(200)
    }

    @Test
    fun onFailure_reducesMaxCount() {
        config.onPollFailure()
        assertThat(config.maxCount).isEqualTo(5)
    }

    @Test
    fun onFailureAfterStable_dropsToConservative() {
        // Start stable, then fail
        assertThat(config.maxCount).isEqualTo(50)
        config.onPollFailure()
        assertThat(config.maxCount).isEqualTo(5)
    }

    @Test
    fun multipleReconnections_alwaysResetsToConservative() {
        // First reconnection
        config.onReconnected()
        repeat(20) { config.onSuccessfulPoll() }
        assertThat(config.maxCount).isEqualTo(50)

        // Second reconnection
        config.onReconnected()
        assertThat(config.maxCount).isEqualTo(5)
    }

    @Test
    fun increaseSteps_areGradual() {
        config.onReconnected()
        val counts = mutableListOf(config.maxCount)

        repeat(10) {
            config.onSuccessfulPoll()
            counts.add(config.maxCount)
        }

        // Each step should be >= previous (monotonically increasing)
        for (i in 1 until counts.size) {
            assertThat(counts[i]).isAtLeast(counts[i - 1])
        }
    }

    @Test
    fun customInitialValues() {
        val custom = AdaptiveBatchConfig(
            stableMaxCount = 100,
            conservativeMaxCount = 2,
            maxUpperBound = 500
        )
        assertThat(custom.maxCount).isEqualTo(100)

        custom.onReconnected()
        assertThat(custom.maxCount).isEqualTo(2)
    }
}
