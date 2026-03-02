"""Tests for InstanceStore."""

import unittest
import threading

from instance_manager.src.instance_store import (
    InstanceStore,
    CREATING,
    RUNNING,
    ERROR,
)


class InstanceStoreTest(unittest.TestCase):

    def _make_store_with_instance(self, name="test-1"):
        store = InstanceStore()
        record = store.create(
            name=name,
            emulator_console_port=5554,
            adb_port=5555,
            aa_forward_port=5277,
            headful=False,
            created_at_ms=1000,
            avd_name="test_avd",
        )
        return store, record

    def test_create_and_get(self):
        store, record = self._make_store_with_instance()
        self.assertEqual(record.name, "test-1")
        self.assertEqual(record.state, CREATING)
        retrieved = store.get("test-1")
        self.assertIs(retrieved, record)

    def test_create_duplicate_raises(self):
        store, _ = self._make_store_with_instance()
        with self.assertRaises(ValueError):
            store.create(
                name="test-1",
                emulator_console_port=5556,
                adb_port=5557,
                aa_forward_port=5278,
                headful=False,
                created_at_ms=2000,
                avd_name="test_avd",
            )

    def test_list_empty(self):
        store = InstanceStore()
        self.assertEqual(store.list_all(), [])

    def test_list_all(self):
        store = InstanceStore()
        store.create("a", 5554, 5555, 5277, False, 1000, "avd")
        store.create("b", 5556, 5557, 5278, False, 2000, "avd")
        self.assertEqual(len(store.list_all()), 2)

    def test_update(self):
        store, _ = self._make_store_with_instance()
        store.update("test-1", state=RUNNING, emulator_pid=1234)
        record = store.get("test-1")
        self.assertEqual(record.state, RUNNING)
        self.assertEqual(record.emulator_pid, 1234)

    def test_update_nonexistent_raises(self):
        store = InstanceStore()
        with self.assertRaises(KeyError):
            store.update("missing", state=RUNNING)

    def test_update_invalid_field_raises(self):
        store, _ = self._make_store_with_instance()
        with self.assertRaises(AttributeError):
            store.update("test-1", nonexistent_field=42)

    def test_remove(self):
        store, _ = self._make_store_with_instance()
        store.remove("test-1")
        self.assertIsNone(store.get("test-1"))

    def test_remove_nonexistent_raises(self):
        store = InstanceStore()
        with self.assertRaises(KeyError):
            store.remove("missing")

    def test_get_running(self):
        store = InstanceStore()
        store.create("a", 5554, 5555, 5277, False, 1000, "avd")
        store.create("b", 5556, 5557, 5278, False, 2000, "avd")
        store.update("a", state=RUNNING)
        store.update("b", state=ERROR)
        running = store.get_running()
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].name, "a")

    def test_get_nonexistent_returns_none(self):
        store = InstanceStore()
        self.assertIsNone(store.get("missing"))

    def test_thread_safety(self):
        store = InstanceStore()
        errors = []

        def create_instances(prefix):
            for i in range(10):
                try:
                    store.create(f"{prefix}-{i}", 5554, 5555, 5277, False, 1000, "avd")
                except ValueError:
                    errors.append(f"Duplicate: {prefix}-{i}")

        threads = [
            threading.Thread(target=create_instances, args=(f"t{t}",))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(store.list_all()), 40)


if __name__ == "__main__":
    unittest.main()
