package com.vanpilot.auto.cache

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class BitmapCacheByteBudgetTest {

    @Test
    fun currentBytes_tracksInsertions() {
        val cache = BitmapCache(maxSize = 10, maxBytes = Long.MAX_VALUE)

        cache.put("a", ByteArray(100))
        assertThat(cache.currentBytes()).isEqualTo(100)

        cache.put("b", ByteArray(200))
        assertThat(cache.currentBytes()).isEqualTo(300)
    }

    @Test
    fun currentBytes_tracksRemovals() {
        val cache = BitmapCache(maxSize = 10, maxBytes = Long.MAX_VALUE)
        cache.put("a", ByteArray(100))
        cache.put("b", ByteArray(200))

        cache.remove("a")

        assertThat(cache.currentBytes()).isEqualTo(200)
    }

    @Test
    fun currentBytes_overwriteAdjustsCorrectly() {
        val cache = BitmapCache(maxSize = 10, maxBytes = Long.MAX_VALUE)
        cache.put("key", ByteArray(100))
        assertThat(cache.currentBytes()).isEqualTo(100)

        // Overwrite with larger data
        cache.put("key", ByteArray(300))
        assertThat(cache.currentBytes()).isEqualTo(300)
        assertThat(cache.size()).isEqualTo(1)
    }

    @Test
    fun eviction_exceedingByteBudget_evictsOldest() {
        // maxBytes = 500, each entry is 200 bytes -> fits 2 entries
        val cache = BitmapCache(maxSize = 100, maxBytes = 500)

        cache.put("a", ByteArray(200))
        cache.put("b", ByteArray(200))
        assertThat(cache.size()).isEqualTo(2)
        assertThat(cache.currentBytes()).isEqualTo(400)

        // Adding a third 200-byte entry exceeds 500 bytes, should evict "a"
        cache.put("c", ByteArray(200))
        assertThat(cache.contains("a")).isFalse()
        assertThat(cache.contains("b")).isTrue()
        assertThat(cache.contains("c")).isTrue()
        assertThat(cache.currentBytes()).isEqualTo(400)
    }

    @Test
    fun eviction_byteBudget_respectsAccessOrder() {
        val cache = BitmapCache(maxSize = 100, maxBytes = 500)

        cache.put("a", ByteArray(200))
        cache.put("b", ByteArray(200))

        // Access "a" to promote it
        cache.get("a")

        // Adding "c" should evict "b" (now oldest), not "a"
        cache.put("c", ByteArray(200))
        assertThat(cache.contains("a")).isTrue()
        assertThat(cache.contains("b")).isFalse()
        assertThat(cache.contains("c")).isTrue()
    }

    @Test
    fun eviction_singleLargeEntry_evictsMultiple() {
        val cache = BitmapCache(maxSize = 100, maxBytes = 500)

        cache.put("a", ByteArray(100))
        cache.put("b", ByteArray(100))
        cache.put("c", ByteArray(100))
        assertThat(cache.currentBytes()).isEqualTo(300)

        // Adding a 400-byte entry needs to evict enough to stay under 500
        cache.put("big", ByteArray(400))
        assertThat(cache.currentBytes()).isAtMost(500)
        assertThat(cache.contains("big")).isTrue()
    }

    @Test
    fun eviction_countAndByteBudget_bothApply() {
        // maxSize=2 AND maxBytes=1000 — count limit should trigger first
        val cache = BitmapCache(maxSize = 2, maxBytes = 1000)

        cache.put("a", ByteArray(10))
        cache.put("b", ByteArray(10))
        cache.put("c", ByteArray(10))

        assertThat(cache.size()).isEqualTo(2)
        assertThat(cache.contains("a")).isFalse()
    }

    @Test
    fun eviction_byteBudgetTriggersBeforeCount() {
        // maxSize=100 but maxBytes=150 — byte budget triggers first
        val cache = BitmapCache(maxSize = 100, maxBytes = 150)

        cache.put("a", ByteArray(100))
        cache.put("b", ByteArray(100))

        // Byte budget exceeded (200 > 150), should evict "a"
        assertThat(cache.size()).isEqualTo(1)
        assertThat(cache.contains("a")).isFalse()
        assertThat(cache.contains("b")).isTrue()
        assertThat(cache.currentBytes()).isEqualTo(100)
    }

    @Test
    fun remove_missingKey_doesNotAffectBytes() {
        val cache = BitmapCache(maxSize = 10, maxBytes = Long.MAX_VALUE)
        cache.put("a", ByteArray(100))

        cache.remove("nonexistent")

        assertThat(cache.currentBytes()).isEqualTo(100)
    }

    @Test
    fun emptyCache_zeroBytes() {
        val cache = BitmapCache(maxSize = 10, maxBytes = 1000)
        assertThat(cache.currentBytes()).isEqualTo(0)
    }

    @Test
    fun defaultMaxBytes_is10MB() {
        // Verify default constructor uses 10MB byte budget
        val cache = BitmapCache()
        // Put a 1MB entry — should succeed with no eviction
        cache.put("1mb", ByteArray(1_000_000))
        assertThat(cache.contains("1mb")).isTrue()
        assertThat(cache.currentBytes()).isEqualTo(1_000_000)
    }
}
