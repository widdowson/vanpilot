"""Tests for the BitmapCacheTracker."""

import unittest
import threading

from supervisor.src.bitmap_cache_tracker import BitmapCacheTracker


class BitmapCacheTrackerStoreTest(unittest.TestCase):
    """Tests for bitmap storage."""

    def setUp(self):
        self.tracker = BitmapCacheTracker()

    def test_store_and_get_bitmap(self):
        """Stored bitmap is retrievable by cache key."""
        data = b"\x89PNG fake"
        self.tracker.store_bitmap("0xABCD1234", data)
        self.assertEqual(self.tracker.get_bitmap("0xABCD1234"), data)

    def test_get_missing_key_returns_none(self):
        """Getting a non-existent key returns None."""
        self.assertIsNone(self.tracker.get_bitmap("0xNONE"))

    def test_has_bitmap_true_when_stored(self):
        self.tracker.store_bitmap("0xAABB", b"data")
        self.assertTrue(self.tracker.has_bitmap("0xAABB"))

    def test_has_bitmap_false_when_missing(self):
        self.assertFalse(self.tracker.has_bitmap("0xNOPE"))

    def test_all_keys_returns_stored_keys(self):
        self.tracker.store_bitmap("0xA", b"a")
        self.tracker.store_bitmap("0xB", b"b")
        self.assertEqual(self.tracker.all_keys(), {"0xA", "0xB"})

    def test_all_keys_empty_initially(self):
        self.assertEqual(self.tracker.all_keys(), set())

    def test_overwrite_bitmap(self):
        """Storing same key twice overwrites the data."""
        self.tracker.store_bitmap("0xA", b"old")
        self.tracker.store_bitmap("0xA", b"new")
        self.assertEqual(self.tracker.get_bitmap("0xA"), b"new")


class BitmapCacheTrackerSentTrackingTest(unittest.TestCase):
    """Tests for tracking which keys have been sent to clients (AC-7.3)."""

    def setUp(self):
        self.tracker = BitmapCacheTracker()

    def test_mark_sent_and_get_sent_keys(self):
        """After marking keys sent, get_sent_keys returns them."""
        self.tracker.mark_sent("client-1", "0xA")
        self.tracker.mark_sent("client-1", "0xB")
        self.assertEqual(self.tracker.get_sent_keys("client-1"), {"0xA", "0xB"})

    def test_sent_keys_are_per_client(self):
        """Different clients track independently."""
        self.tracker.mark_sent("client-1", "0xA")
        self.tracker.mark_sent("client-2", "0xB")
        self.assertEqual(self.tracker.get_sent_keys("client-1"), {"0xA"})
        self.assertEqual(self.tracker.get_sent_keys("client-2"), {"0xB"})

    def test_unknown_client_returns_empty_set(self):
        self.assertEqual(self.tracker.get_sent_keys("unknown"), set())

    def test_clear_client_removes_sent_keys(self):
        self.tracker.mark_sent("client-1", "0xA")
        self.tracker.clear_client("client-1")
        self.assertEqual(self.tracker.get_sent_keys("client-1"), set())

    def test_clear_client_does_not_affect_others(self):
        self.tracker.mark_sent("client-1", "0xA")
        self.tracker.mark_sent("client-2", "0xB")
        self.tracker.clear_client("client-1")
        self.assertEqual(self.tracker.get_sent_keys("client-2"), {"0xB"})


class BitmapCacheTrackerReconcileTest(unittest.TestCase):
    """Tests for cache reconciliation on reconnection (AC-7.4)."""

    def setUp(self):
        self.tracker = BitmapCacheTracker()

    def test_reconcile_returns_missing_keys(self):
        """Reconcile returns keys the supervisor has but the client doesn't."""
        self.tracker.store_bitmap("0xA", b"a")
        self.tracker.store_bitmap("0xB", b"b")
        self.tracker.store_bitmap("0xC", b"c")
        missing = self.tracker.reconcile("client-1", {"0xA", "0xC"})
        self.assertEqual(missing, {"0xB"})

    def test_reconcile_empty_client_returns_all_keys(self):
        """If client has nothing, all keys are missing."""
        self.tracker.store_bitmap("0xA", b"a")
        self.tracker.store_bitmap("0xB", b"b")
        missing = self.tracker.reconcile("client-1", set())
        self.assertEqual(missing, {"0xA", "0xB"})

    def test_reconcile_client_has_everything(self):
        """If client has all keys, nothing is missing."""
        self.tracker.store_bitmap("0xA", b"a")
        missing = self.tracker.reconcile("client-1", {"0xA"})
        self.assertEqual(missing, set())

    def test_reconcile_updates_sent_keys(self):
        """After reconciliation, sent keys are updated to match client's state."""
        self.tracker.store_bitmap("0xA", b"a")
        self.tracker.mark_sent("client-1", "0xOLD")
        self.tracker.reconcile("client-1", {"0xA"})
        self.assertEqual(self.tracker.get_sent_keys("client-1"), {"0xA"})

    def test_reconcile_no_bitmaps_stored(self):
        """If supervisor has nothing, nothing is missing."""
        missing = self.tracker.reconcile("client-1", {"0xA"})
        self.assertEqual(missing, set())


class BitmapCacheTrackerThreadSafetyTest(unittest.TestCase):
    """Verify thread safety basics."""

    def test_concurrent_store_and_get(self):
        """Basic concurrent access should not crash."""
        tracker = BitmapCacheTracker()
        errors = []

        def writer():
            try:
                for i in range(100):
                    tracker.store_bitmap(f"0x{i:04X}", f"data-{i}".encode())
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    tracker.get_bitmap(f"0x{i:04X}")
                    tracker.all_keys()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
