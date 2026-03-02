package com.vanpilot.auto.cache

/**
 * Thread-safe in-memory LRU cache mapping cache keys to PNG image data.
 *
 * Uses access-order LinkedHashMap so that recently accessed entries
 * are evicted last when the cache exceeds [maxSize] entries or
 * [maxBytes] total byte budget.
 *
 * @param maxSize Maximum number of entries (default 64).
 * @param maxBytes Maximum total bytes of image data. Default 10 MB.
 *                 Pass [Long.MAX_VALUE] to disable byte-budget eviction.
 */
class BitmapCache(
    private val maxSize: Int = 64,
    private val maxBytes: Long = 10L * 1024 * 1024
) {

    private val cache = LinkedHashMap<String, ByteArray>(16, 0.75f, true)
    private val lock = Any()
    private var currentBytes: Long = 0

    fun put(key: String, data: ByteArray) {
        synchronized(lock) {
            val existing = cache.put(key, data)
            if (existing != null) {
                currentBytes -= existing.size
            }
            currentBytes += data.size
            trimToSize()
        }
    }

    fun get(key: String): ByteArray? {
        synchronized(lock) {
            return cache[key]
        }
    }

    fun contains(key: String): Boolean {
        synchronized(lock) {
            return cache.containsKey(key)
        }
    }

    fun keys(): Set<String> {
        synchronized(lock) {
            return cache.keys.toSet()
        }
    }

    fun remove(key: String): ByteArray? {
        synchronized(lock) {
            val removed = cache.remove(key)
            if (removed != null) {
                currentBytes -= removed.size
            }
            return removed
        }
    }

    fun size(): Int {
        synchronized(lock) {
            return cache.size
        }
    }

    /** Total bytes of image data currently in the cache. */
    fun currentBytes(): Long {
        synchronized(lock) {
            return currentBytes
        }
    }

    private fun trimToSize() {
        while (cache.size > maxSize || (cache.isNotEmpty() && currentBytes > maxBytes)) {
            val eldest = cache.entries.iterator().next()
            currentBytes -= eldest.value.size
            cache.remove(eldest.key)
        }
    }
}
