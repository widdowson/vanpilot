package com.vanpilot.auto.cache

/**
 * Thread-safe in-memory LRU cache mapping cache keys to PNG image data.
 *
 * Uses access-order LinkedHashMap so that recently accessed entries
 * are evicted last when the cache exceeds [maxSize].
 */
class BitmapCache(private val maxSize: Int = 64) {

    private val cache = LinkedHashMap<String, ByteArray>(16, 0.75f, true)
    private val lock = Any()

    fun put(key: String, data: ByteArray) {
        synchronized(lock) {
            cache[key] = data
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
            return cache.remove(key)
        }
    }

    fun size(): Int {
        synchronized(lock) {
            return cache.size
        }
    }

    private fun trimToSize() {
        while (cache.size > maxSize) {
            val eldest = cache.entries.iterator().next()
            cache.remove(eldest.key)
        }
    }
}
