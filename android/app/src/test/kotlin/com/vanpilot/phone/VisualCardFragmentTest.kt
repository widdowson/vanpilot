package com.vanpilot.phone

import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.widget.ImageView
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.R
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode

/**
 * Robolectric tests for VisualCardFragment.
 * Verifies bitmap display and placeholder rendering.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class VisualCardFragmentTest {

    private lateinit var activity: PhoneMainActivity
    private lateinit var fragment: VisualCardFragment

    @Suppress("DEPRECATION")
    @Before
    fun setUp() {
        activity = Robolectric.buildActivity(PhoneMainActivity::class.java)
            .create()
            .start()
            .resume()
            .get()
        // The default fragment is VisualCardFragment
        fragment = activity.fragmentManager
            .findFragmentById(R.id.fragment_container) as VisualCardFragment
    }

    @Test
    fun fragment_isCreated() {
        assertThat(fragment).isNotNull()
    }

    @Test
    fun fragment_hasImageView() {
        val imageView = fragment.view!!.findViewById<ImageView>(R.id.visual_card_image)
        assertThat(imageView).isNotNull()
    }

    @Test
    fun displayBitmap_setsImageOnImageView() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        fragment.displayBitmap(bitmap)

        val imageView = fragment.view!!.findViewById<ImageView>(R.id.visual_card_image)
        val drawable = imageView.drawable as? BitmapDrawable
        assertThat(drawable).isNotNull()
        assertThat(drawable!!.bitmap).isEqualTo(bitmap)
    }

    @Test
    fun clearBitmap_removesImageFromImageView() {
        val bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888)
        fragment.displayBitmap(bitmap)
        fragment.clearBitmap()

        val imageView = fragment.view!!.findViewById<ImageView>(R.id.visual_card_image)
        assertThat(imageView.drawable).isNull()
    }

    @Test
    fun fragment_initialImageViewHasNoDrawable() {
        val imageView = fragment.view!!.findViewById<ImageView>(R.id.visual_card_image)
        assertThat(imageView.drawable).isNull()
    }
}
