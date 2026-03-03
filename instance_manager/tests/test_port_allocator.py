"""Tests for PortAllocator."""

import unittest
import threading

from instance_manager.src.port_allocator import PortAllocator


class PortAllocatorTest(unittest.TestCase):

    def test_first_slot(self):
        pa = PortAllocator(max_slots=4)
        slot = pa.allocate()
        self.assertEqual(slot.slot_index, 0)
        self.assertEqual(slot.console_port, 5554)
        self.assertEqual(slot.adb_port, 5555)
        self.assertEqual(slot.aa_forward_port, 5277)

    def test_second_slot(self):
        pa = PortAllocator(max_slots=4)
        pa.allocate()
        slot = pa.allocate()
        self.assertEqual(slot.slot_index, 1)
        self.assertEqual(slot.console_port, 5556)
        self.assertEqual(slot.adb_port, 5557)
        self.assertEqual(slot.aa_forward_port, 5278)

    def test_release_and_reuse(self):
        pa = PortAllocator(max_slots=4)
        slot0 = pa.allocate()
        pa.allocate()  # slot 1
        pa.release(slot0.slot_index)
        reused = pa.allocate()
        self.assertEqual(reused.slot_index, 0)

    def test_exhaust_slots(self):
        pa = PortAllocator(max_slots=2)
        pa.allocate()
        pa.allocate()
        with self.assertRaises(RuntimeError):
            pa.allocate()

    def test_release_invalid_slot(self):
        pa = PortAllocator(max_slots=4)
        with self.assertRaises(ValueError):
            pa.release(0)

    def test_thread_safety(self):
        pa = PortAllocator(max_slots=100)
        results = []
        errors = []

        def allocate_many():
            for _ in range(25):
                try:
                    results.append(pa.allocate())
                except RuntimeError as e:
                    errors.append(e)

        threads = [threading.Thread(target=allocate_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 100)
        # All slot indices should be unique
        indices = {s.slot_index for s in results}
        self.assertEqual(len(indices), 100)


if __name__ == "__main__":
    unittest.main()
