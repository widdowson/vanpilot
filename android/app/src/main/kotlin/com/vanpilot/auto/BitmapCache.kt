package com.vanpilot.auto

import android.graphics.Bitmap
import java.util.concurrent.ConcurrentHashMap

/**
 * Thread-safe in-memory cache for bitmaps received via gRPC BitmapPayload events.
 *
 * Keyed by the hex cache key (e.g., "0xDEADBEEF") assigned by the MCP server.
 * Uses ConcurrentHashMap for safe access from both the gRPC polling thread (put)
 * and the UI thread (get/has).
 */
class BitmapCache {
    private val cache = ConcurrentHashMap<String, Bitmap>()

    fun put(cacheKey: String, bitmap: Bitmap) {
        cache[cacheKey] = bitmap
    }

    fun get(cacheKey: String): Bitmap? = cache[cacheKey]

    fun has(cacheKey: String): Boolean = cache.containsKey(cacheKey)

    fun keys(): Set<String> = cache.keys.toSet()

    val size: Int get() = cache.size

    fun remove(cacheKey: String): Bitmap? = cache.remove(cacheKey)

    fun clear() = cache.clear()
}
