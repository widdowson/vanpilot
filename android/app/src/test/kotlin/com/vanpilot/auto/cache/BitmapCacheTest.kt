package com.vanpilot.auto.cache

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class BitmapCacheTest {

    private lateinit var cache: BitmapCache

    @Before
    fun setUp() {
        cache = BitmapCache(maxSize = 4)
    }

    @Test
    fun initialState_isEmpty() {
        assertThat(cache.size()).isEqualTo(0)
        assertThat(cache.keys()).isEmpty()
    }

    @Test
    fun put_thenGet_returnsData() {
        val data = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47) // PNG magic
        cache.put("0xDEAD", data)
        assertThat(cache.get("0xDEAD")).isEqualTo(data)
    }

    @Test
    fun get_missingKey_returnsNull() {
        assertThat(cache.get("nonexistent")).isNull()
    }

    @Test
    fun contains_presentKey_returnsTrue() {
        cache.put("0xBEEF", byteArrayOf(1, 2, 3))
        assertThat(cache.contains("0xBEEF")).isTrue()
    }

    @Test
    fun contains_missingKey_returnsFalse() {
        assertThat(cache.contains("0xBEEF")).isFalse()
    }

    @Test
    fun keys_returnsAllKeys() {
        cache.put("a", byteArrayOf(1))
        cache.put("b", byteArrayOf(2))
        cache.put("c", byteArrayOf(3))
        assertThat(cache.keys()).containsExactly("a", "b", "c")
    }

    @Test
    fun remove_existingKey_returnsData() {
        val data = byteArrayOf(1, 2, 3)
        cache.put("key", data)
        assertThat(cache.remove("key")).isEqualTo(data)
        assertThat(cache.contains("key")).isFalse()
    }

    @Test
    fun remove_missingKey_returnsNull() {
        assertThat(cache.remove("nonexistent")).isNull()
    }

    @Test
    fun eviction_removesOldestWhenFull() {
        // maxSize is 4
        cache.put("a", byteArrayOf(1))
        cache.put("b", byteArrayOf(2))
        cache.put("c", byteArrayOf(3))
        cache.put("d", byteArrayOf(4))
        assertThat(cache.size()).isEqualTo(4)

        // Adding a 5th entry should evict "a" (oldest)
        cache.put("e", byteArrayOf(5))
        assertThat(cache.size()).isEqualTo(4)
        assertThat(cache.contains("a")).isFalse()
        assertThat(cache.contains("e")).isTrue()
    }

    @Test
    fun eviction_accessOrderPromotesEntry() {
        cache.put("a", byteArrayOf(1))
        cache.put("b", byteArrayOf(2))
        cache.put("c", byteArrayOf(3))
        cache.put("d", byteArrayOf(4))

        // Access "a" to promote it in LRU order
        cache.get("a")

        // Adding a 5th entry should evict "b" (now oldest), not "a"
        cache.put("e", byteArrayOf(5))
        assertThat(cache.contains("a")).isTrue()
        assertThat(cache.contains("b")).isFalse()
    }

    @Test
    fun put_overwritesExistingKey() {
        cache.put("key", byteArrayOf(1))
        cache.put("key", byteArrayOf(2))
        assertThat(cache.get("key")).isEqualTo(byteArrayOf(2))
        assertThat(cache.size()).isEqualTo(1)
    }

    @Test
    fun size_tracksInsertionsAndRemovals() {
        cache.put("a", byteArrayOf(1))
        cache.put("b", byteArrayOf(2))
        assertThat(cache.size()).isEqualTo(2)
        cache.remove("a")
        assertThat(cache.size()).isEqualTo(1)
    }
}
