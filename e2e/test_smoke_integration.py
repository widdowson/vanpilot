"""Full-stack E2E smoke test.

Requires a running instance manager and (optionally) Android SDK.
Tagged manual/exclusive — not run during `bazel test //...`.

The test verifies the complete pipeline:
  MCP submit_bitmap → supervisor events → gRPC GetEvents → display on head unit

Usage:
  bazel test //e2e:smoke_integration_test \
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061 \
    --test_env=VANPILOT_APK=bazel-bin/android/vanpilot.apk

  # Without APK (emulator snapshot already has app):
  bazel test //e2e:smoke_integration_test \
    --test_env=INSTANCE_MANAGER_ADDR=localhost:50061
"""

import os
import struct
import unittest

import grpc

from e2e.smoke_test_runner import SmokeTestRunner


INSTANCE_MANAGER_ADDR = os.environ.get("INSTANCE_MANAGER_ADDR", "localhost:50061")


def _instance_manager_reachable() -> bool:
    """Check if the instance manager is reachable."""
    try:
        channel = grpc.insecure_channel(INSTANCE_MANAGER_ADDR)
        grpc.channel_ready_future(channel).result(timeout=3)
        channel.close()
        return True
    except grpc.FutureTimeoutError:
        return False
    except Exception:
        return False


@unittest.skipUnless(
    _instance_manager_reachable(),
    f"Instance manager not reachable at {INSTANCE_MANAGER_ADDR}",
)
class SmokeIntegrationTest(unittest.TestCase):
    """Full-stack smoke test with real emulator+DHU."""

    runner: SmokeTestRunner = None

    @classmethod
    def setUpClass(cls):
        cls.runner = SmokeTestRunner(
            instance_manager_addr=INSTANCE_MANAGER_ADDR,
            instance_name="e2e-smoke",
        )
        cls.runner.setup()

    @classmethod
    def tearDownClass(cls):
        if cls.runner:
            cls.runner.teardown()

    def test_instance_created_successfully(self):
        """Verify the instance manager created a RUNNING emulator."""
        info = self.runner.instance_info
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "e2e-smoke")
        self.assertGreater(info.emulator_console_port, 0)
        self.assertGreater(info.adb_port, 0)

    def test_submit_and_display_bitmap(self):
        """Submit a test bitmap via MCP and verify it creates events."""
        cache_key = self.runner.submit_and_display_test_bitmap()
        self.assertTrue(cache_key.startswith("0x"))

        # Verify display_command event exists
        found = self.runner.verify_display_command_in_events(cache_key)
        self.assertTrue(found, "DisplayCommand not found in events")

    def test_bitmap_retrievable(self):
        """Verify the submitted bitmap can be fetched via GetBitmap."""
        cache_key = self.runner.submit_and_display_test_bitmap()
        retrievable = self.runner.verify_bitmap_retrievable(cache_key)
        self.assertTrue(retrievable, "Bitmap not retrievable via GetBitmap")

    def test_dhu_screenshot_is_valid_png(self):
        """Capture DHU screenshot and verify it's a valid PNG."""
        png = self.runner.capture_dhu_screenshot()
        self.assertTrue(
            png.startswith(b"\x89PNG\r\n\x1a\n"),
            "DHU screenshot is not a valid PNG",
        )
        self.assertGreater(len(png), 1024, "Screenshot too small")

        # Save to test outputs
        undeclared = os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR")
        if undeclared:
            os.makedirs(undeclared, exist_ok=True)
            path = os.path.join(undeclared, "dhu_smoke_screenshot.png")
            with open(path, "wb") as f:
                f.write(png)

    def test_full_pipeline_mcp_to_events_to_bitmap(self):
        """Full pipeline: submit → display → verify events → fetch bitmap."""
        # Submit and display
        cache_key = self.runner.submit_and_display_test_bitmap()

        # Pull events (as Android app would)
        events = self.runner.get_events()
        bitmap_events = [
            e for e in events
            if e.WhichOneof("payload") == "bitmap_payload"
        ]
        display_events = [
            e for e in events
            if e.WhichOneof("payload") == "display_command"
        ]

        self.assertGreater(len(bitmap_events), 0, "No BitmapPayload events")
        self.assertGreater(len(display_events), 0, "No DisplayCommand events")

        # Verify the display command references our cache key
        display_keys = {e.display_command.cache_key for e in display_events}
        self.assertIn(cache_key, display_keys)

        # Fetch bitmap (as Android app would if missing from cache)
        retrievable = self.runner.verify_bitmap_retrievable(cache_key)
        self.assertTrue(retrievable)


if __name__ == "__main__":
    unittest.main()
