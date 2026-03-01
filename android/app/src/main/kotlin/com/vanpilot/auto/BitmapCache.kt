package com.vanpilot.auto

import android.graphics.Bitmap

/**
 * In-memory cache for bitmaps received via gRPC BitmapPayload events.
 *
 * Keyed by the hex cache key (e.g., "0xDEADBEEF") assigned by the MCP server.
 * The Android app decodes PNG bytes into Bitmap objects and stores them here
 * so that DisplayCommand events can reference them by key without retransmission.
 */
class BitmapCache {
    private val cache = mutableMapOf<String, Bitmap>()

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
