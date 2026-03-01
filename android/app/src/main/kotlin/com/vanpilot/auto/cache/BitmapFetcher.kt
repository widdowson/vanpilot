package com.vanpilot.auto.cache

/**
 * Interface for fetching missing bitmaps from the supervisor (AC-7.2).
 *
 * When a DisplayCommand references a cache key not in BitmapCache,
 * the EventProcessor calls fetchBitmap to request it from the server.
 */
fun interface BitmapFetcher {
    /**
     * Fetch bitmap data for the given cache key.
     *
     * @return The PNG image data, or null if the bitmap is unavailable.
     */
    fun fetchBitmap(cacheKey: String): ByteArray?
}
