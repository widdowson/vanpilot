package com.vanpilot.auto.cache

/**
 * Tracks the ordered history of displayed cache keys, supporting
 * back/forward navigation like a browser history.
 *
 * Thread-safe via synchronized blocks on the internal lock.
 *
 * @param maxSize Maximum number of entries to retain. Oldest entries
 *                are evicted when exceeded.
 */
class DisplayHistory(private val maxSize: Int = 50) {

    private val lock = Any()
    private val entries = mutableListOf<String>()
    private var currentIndex = -1

    fun addEntry(key: String) {
        synchronized(lock) {
            // Skip duplicate consecutive entries
            if (currentIndex >= 0 && entries[currentIndex] == key) return

            // Truncate forward history
            if (currentIndex < entries.size - 1) {
                entries.subList(currentIndex + 1, entries.size).clear()
            }

            entries.add(key)
            currentIndex = entries.size - 1

            // Evict oldest if over max size
            while (entries.size > maxSize) {
                entries.removeAt(0)
                currentIndex--
            }
        }
    }

    fun canGoBack(): Boolean {
        synchronized(lock) {
            return currentIndex > 0
        }
    }

    fun canGoForward(): Boolean {
        synchronized(lock) {
            return currentIndex < entries.size - 1
        }
    }

    fun goBack(): String? {
        synchronized(lock) {
            if (!canGoBack()) return null
            currentIndex--
            return entries[currentIndex]
        }
    }

    fun goForward(): String? {
        synchronized(lock) {
            if (!canGoForward()) return null
            currentIndex++
            return entries[currentIndex]
        }
    }

    fun currentKey(): String? {
        synchronized(lock) {
            return if (currentIndex >= 0 && currentIndex < entries.size) entries[currentIndex] else null
        }
    }
}
