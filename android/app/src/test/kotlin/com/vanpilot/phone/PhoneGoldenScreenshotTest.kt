package com.vanpilot.phone

import android.graphics.Bitmap
import android.view.View
import com.google.android.material.tabs.TabLayout
import com.google.common.truth.Truth.assertThat
import com.vanpilot.auto.R
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode
import java.io.File
import java.io.FileOutputStream

/**
 * Golden screenshot tests for the phone UI.
 *
 * Renders the phone UI via Robolectric, captures bitmaps, and compares
 * against committed golden PNGs in goldens/phone/. On first run (or when
 * UPDATE_GOLDENS=true), writes new golden files to the output directory.
 *
 * To update goldens:
 *   bazel test //android:phone_golden_screenshot_test --test_env=UPDATE_GOLDENS=true
 *
 * Golden files are then copied from bazel-testlogs into goldens/phone/.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
@ConscryptMode(ConscryptMode.Mode.OFF)
class PhoneGoldenScreenshotTest {

    private lateinit var activity: PhoneMainActivity

    companion object {
        private const val SCREENSHOT_WIDTH = 1080
        private const val SCREENSHOT_HEIGHT = 1920

        private fun goldenDir(): String {
            val runfiles = System.getenv("TEST_SRCDIR")
            val workspace = System.getenv("TEST_WORKSPACE") ?: "__main__"
            return if (runfiles != null) {
                "$runfiles/$workspace/goldens/phone"
            } else {
                "goldens/phone"
            }
        }

        private fun outputDir(): String {
            val undeclaredOutputs = System.getenv("TEST_UNDECLARED_OUTPUTS_DIR")
            return undeclaredOutputs ?: "/tmp/phone_goldens"
        }

        private fun shouldUpdateGoldens(): Boolean {
            return System.getenv("UPDATE_GOLDENS")?.lowercase() == "true"
        }
    }

    @Before
    fun setUp() {
        activity = org.robolectric.Robolectric.buildActivity(PhoneMainActivity::class.java)
            .create()
            .start()
            .resume()
            .get()
    }

    @Test
    fun golden_visualTabDefault() {
        activity.supportFragmentManager.executePendingTransactions()
        val bitmap = captureActivity()
        assertGoldenMatch("phone_visual_tab_default.png", bitmap)
    }

    @Test
    fun golden_leadAgentConversation() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        tabLayout.getTabAt(1)?.select()
        activity.supportFragmentManager.executePendingTransactions()
        val bitmap = captureActivity()
        assertGoldenMatch("phone_lead_agent_conversation.png", bitmap)
    }

    @Test
    fun golden_subAgentResearcher() {
        val tabLayout = activity.findViewById<TabLayout>(R.id.tab_layout)
        tabLayout.getTabAt(2)?.select()
        activity.supportFragmentManager.executePendingTransactions()
        val bitmap = captureActivity()
        assertGoldenMatch("phone_sub_agent_researcher.png", bitmap)
    }

    @Test
    fun golden_connectionStatusConnected() {
        activity.updateConnectionStatus(true)
        activity.supportFragmentManager.executePendingTransactions()
        val bitmap = captureActivity()
        assertGoldenMatch("phone_connection_connected.png", bitmap)
    }

    @Test
    fun golden_connectionStatusDisconnected() {
        activity.updateConnectionStatus(false)
        activity.supportFragmentManager.executePendingTransactions()
        val bitmap = captureActivity()
        assertGoldenMatch("phone_connection_disconnected.png", bitmap)
    }

    private fun captureActivity(): Bitmap {
        val decorView = activity.window.decorView
        decorView.measure(
            View.MeasureSpec.makeMeasureSpec(SCREENSHOT_WIDTH, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(SCREENSHOT_HEIGHT, View.MeasureSpec.EXACTLY)
        )
        decorView.layout(0, 0, SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT)

        val bitmap = Bitmap.createBitmap(SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = android.graphics.Canvas(bitmap)
        decorView.draw(canvas)
        return bitmap
    }

    private fun assertGoldenMatch(filename: String, actual: Bitmap) {
        val outDir = File(outputDir())
        outDir.mkdirs()

        // Always write actual to undeclared outputs for inspection
        val actualFile = File(outDir, "actual_$filename")
        FileOutputStream(actualFile).use { fos ->
            actual.compress(Bitmap.CompressFormat.PNG, 100, fos)
        }

        if (shouldUpdateGoldens()) {
            // Write as the new golden
            val goldenOut = File(outDir, filename)
            FileOutputStream(goldenOut).use { fos ->
                actual.compress(Bitmap.CompressFormat.PNG, 100, fos)
            }
            println("Updated golden: ${goldenOut.absolutePath}")
            return
        }

        // Compare against committed golden
        val goldenFile = File(goldenDir(), filename)
        if (!goldenFile.exists()) {
            // No golden yet — write it and pass (first run)
            val goldenOut = File(outDir, filename)
            FileOutputStream(goldenOut).use { fos ->
                actual.compress(Bitmap.CompressFormat.PNG, 100, fos)
            }
            println("No golden found at ${goldenFile.absolutePath}. " +
                    "Wrote initial golden to ${goldenOut.absolutePath}. " +
                    "Copy to goldens/phone/ and commit.")
            // Don't fail — allow first-run generation
            return
        }

        val goldenBitmap = android.graphics.BitmapFactory.decodeFile(goldenFile.absolutePath)
        assertThat(goldenBitmap).isNotNull()
        assertThat(actual.width).isEqualTo(goldenBitmap.width)
        assertThat(actual.height).isEqualTo(goldenBitmap.height)

        var diffCount = 0
        for (y in 0 until actual.height) {
            for (x in 0 until actual.width) {
                if (actual.getPixel(x, y) != goldenBitmap.getPixel(x, y)) {
                    diffCount++
                }
            }
        }

        if (diffCount > 0) {
            // Write diff image
            val diffBitmap = Bitmap.createBitmap(actual.width, actual.height, Bitmap.Config.ARGB_8888)
            for (y in 0 until actual.height) {
                for (x in 0 until actual.width) {
                    val actualPx = actual.getPixel(x, y)
                    val goldenPx = goldenBitmap.getPixel(x, y)
                    diffBitmap.setPixel(x, y, if (actualPx != goldenPx) {
                        android.graphics.Color.RED
                    } else {
                        android.graphics.Color.argb(255,
                            android.graphics.Color.red(actualPx) / 3,
                            android.graphics.Color.green(actualPx) / 3,
                            android.graphics.Color.blue(actualPx) / 3)
                    })
                }
            }
            val diffFile = File(outDir, "diff_$filename")
            FileOutputStream(diffFile).use { fos ->
                diffBitmap.compress(Bitmap.CompressFormat.PNG, 100, fos)
            }
            assertThat(diffCount).isEqualTo(0)
        }
    }
}
