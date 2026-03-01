package com.vanpilot.auto.grpc

import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.BitmapCache
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/**
 * Unit tests for SyncClient initialization and adaptive batching logic.
 *
 * Note: Full gRPC integration tests require a running supervisor server
 * and are covered by the Python e2e tests. These tests verify the client's
 * state management and configuration.
 */
@RunWith(JUnit4::class)
class SyncClientTest {

    @Test
    fun defaultMaxCount() {
        assertThat(SyncClient.DEFAULT_MAX_COUNT).isEqualTo(50)
    }

    @Test
    fun reconnectMaxCount() {
        assertThat(SyncClient.RECONNECT_MAX_COUNT).isEqualTo(5)
    }

    @Test
    fun maxBatchSize() {
        assertThat(SyncClient.MAX_BATCH_SIZE).isEqualTo(200)
    }

    @Test
    fun bitmapCacheStartsEmpty() {
        val cache = BitmapCache()
        assertThat(cache.size).isEqualTo(0)
    }
}
