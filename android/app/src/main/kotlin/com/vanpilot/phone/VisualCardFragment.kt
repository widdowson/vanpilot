package com.vanpilot.phone

import androidx.fragment.app.Fragment
import android.graphics.Bitmap
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import com.vanpilot.auto.R

/**
 * Fragment that displays the latest visual card bitmap.
 *
 * Replaces the Android Auto SurfaceCallback approach with a standard
 * ImageView. The bitmap is set programmatically when received via gRPC.
 */
class VisualCardFragment : Fragment() {

    private var imageView: ImageView? = null
    private var pendingBitmap: Bitmap? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return inflater.inflate(R.layout.fragment_visual_card, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        imageView = view.findViewById(R.id.visual_card_image)

        pendingBitmap?.let {
            imageView?.setImageBitmap(it)
            pendingBitmap = null
        }
    }

    fun displayBitmap(bitmap: Bitmap) {
        val iv = imageView
        if (iv != null) {
            iv.setImageBitmap(bitmap)
        } else {
            pendingBitmap = bitmap
        }
    }

    fun clearBitmap() {
        pendingBitmap = null
        imageView?.setImageDrawable(null)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        imageView = null
    }
}
