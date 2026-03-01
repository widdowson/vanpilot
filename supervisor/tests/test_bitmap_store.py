"""Tests for BitmapStore sent-tracking and reconciliation features."""

import unittest
import threading

from supervisor.src.mcp_bridge import BitmapStore


class BitmapStoreSentTrackingTest(unittest.TestCase):
    """Tests for tracking which keys have been sent to clients (AC-7.3)."""

    def setUp(self):
        self.store = BitmapStore()

    def test_mark_sent_and_get_sent_keys(self):
        self.store.mark_sent("client-1", "0xA")
        self.store.mark_sent("client-1", "0xB")
        self.assertEqual(self.store.get_sent_keys("client-1"), {"0xA", "0xB"})

    def test_sent_keys_are_per_client(self):
        self.store.mark_sent("client-1", "0xA")
        self.store.mark_sent("client-2", "0xB")
        self.assertEqual(self.store.get_sent_keys("client-1"), {"0xA"})
        self.assertEqual(self.store.get_sent_keys("client-2"), {"0xB"})

    def test_unknown_client_returns_empty_set(self):
        self.assertEqual(self.store.get_sent_keys("unknown"), set())

    def test_clear_client_removes_sent_keys(self):
        self.store.mark_sent("client-1", "0xA")
        self.store.clear_client("client-1")
        self.assertEqual(self.store.get_sent_keys("client-1"), set())

    def test_clear_client_does_not_affect_others(self):
        self.store.mark_sent("client-1", "0xA")
        self.store.mark_sent("client-2", "0xB")
        self.store.clear_client("client-1")
        self.assertEqual(self.store.get_sent_keys("client-2"), {"0xB"})

    def test_all_keys(self):
        self.store.put("0xA", b"a")
        self.store.put("0xB", b"b")
        self.assertEqual(self.store.all_keys(), {"0xA", "0xB"})

    def test_all_keys_empty_initially(self):
        self.assertEqual(self.store.all_keys(), set())


class BitmapStoreReconcileTest(unittest.TestCase):
    """Tests for cache reconciliation on reconnection (AC-7.4)."""

    def setUp(self):
        self.store = BitmapStore()

    def test_reconcile_returns_missing_keys(self):
        self.store.put("0xA", b"a")
        self.store.put("0xB", b"b")
        self.store.put("0xC", b"c")
        missing = self.store.reconcile("client-1", {"0xA", "0xC"})
        self.assertEqual(missing, {"0xB"})

    def test_reconcile_empty_client_returns_all_keys(self):
        self.store.put("0xA", b"a")
        self.store.put("0xB", b"b")
        missing = self.store.reconcile("client-1", set())
        self.assertEqual(missing, {"0xA", "0xB"})

    def test_reconcile_client_has_everything(self):
        self.store.put("0xA", b"a")
        missing = self.store.reconcile("client-1", {"0xA"})
        self.assertEqual(missing, set())

    def test_reconcile_updates_sent_keys(self):
        self.store.put("0xA", b"a")
        self.store.mark_sent("client-1", "0xOLD")
        self.store.reconcile("client-1", {"0xA"})
        self.assertEqual(self.store.get_sent_keys("client-1"), {"0xA"})

    def test_reconcile_no_bitmaps_stored(self):
        missing = self.store.reconcile("client-1", {"0xA"})
        self.assertEqual(missing, set())


class BitmapStoreThreadSafetyTest(unittest.TestCase):
    """Verify thread safety basics."""

    def test_concurrent_put_and_get(self):
        store = BitmapStore()
        errors = []

        def writer():
            try:
                for i in range(100):
                    store.put(f"0x{i:04X}", f"data-{i}".encode())
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    store.get(f"0x{i:04X}")
                    store.all_keys()
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
