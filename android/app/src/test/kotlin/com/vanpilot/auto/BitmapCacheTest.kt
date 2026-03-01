package com.vanpilot.auto

import android.graphics.Bitmap
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
        cache = BitmapCache()
    }

    @Test
    fun putAndGet() {
        val bitmap = Bitmap.createBitmap(10, 10, Bitmap.Config.ARGB_8888)
        cache.put("0xDEADBEEF", bitmap)
        assertThat(cache.get("0xDEADBEEF")).isSameInstanceAs(bitmap)
    }

    @Test
    fun getMissingReturnsNull() {
        assertThat(cache.get("0xNONEXIST")).isNull()
    }

    @Test
    fun hasKey() {
        assertThat(cache.has("0xDEADBEEF")).isFalse()
        cache.put("0xDEADBEEF", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        assertThat(cache.has("0xDEADBEEF")).isTrue()
    }

    @Test
    fun keys() {
        cache.put("0xAAAA", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        cache.put("0xBBBB", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        assertThat(cache.keys()).containsExactly("0xAAAA", "0xBBBB")
    }

    @Test
    fun size() {
        assertThat(cache.size).isEqualTo(0)
        cache.put("0xAAAA", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        assertThat(cache.size).isEqualTo(1)
    }

    @Test
    fun remove() {
        val bitmap = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888)
        cache.put("0xAAAA", bitmap)
        val removed = cache.remove("0xAAAA")
        assertThat(removed).isSameInstanceAs(bitmap)
        assertThat(cache.has("0xAAAA")).isFalse()
    }

    @Test
    fun clear() {
        cache.put("0xAAAA", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        cache.put("0xBBBB", Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888))
        cache.clear()
        assertThat(cache.size).isEqualTo(0)
    }

    @Test
    fun overwrite() {
        val bitmap1 = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888)
        val bitmap2 = Bitmap.createBitmap(2, 2, Bitmap.Config.ARGB_8888)
        cache.put("0xAAAA", bitmap1)
        cache.put("0xAAAA", bitmap2)
        assertThat(cache.get("0xAAAA")).isSameInstanceAs(bitmap2)
    }
}
