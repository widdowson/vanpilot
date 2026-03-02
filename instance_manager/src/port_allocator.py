"""Port slot allocation for emulator + DHU instances.

Each slot gets three ports:
  console = 5554 + 2 * slot_index
  adb     = console + 1
  aa_fwd  = 5277 + slot_index
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class PortSlot:
    """An allocated set of ports for one emulator + DHU instance."""

    slot_index: int
    console_port: int
    adb_port: int
    aa_forward_port: int


_BASE_CONSOLE = 5554
_BASE_AA_FWD = 5277


class PortAllocator:
    """Thread-safe port slot allocator."""

    def __init__(self, max_slots: int = 8) -> None:
        self._max_slots = max_slots
        self._used: set[int] = set()
        self._lock = threading.Lock()

    def allocate(self) -> PortSlot:
        """Allocate the lowest available port slot.

        Raises:
            RuntimeError: If all slots are in use.
        """
        with self._lock:
            for i in range(self._max_slots):
                if i not in self._used:
                    self._used.add(i)
                    return PortSlot(
                        slot_index=i,
                        console_port=_BASE_CONSOLE + 2 * i,
                        adb_port=_BASE_CONSOLE + 2 * i + 1,
                        aa_forward_port=_BASE_AA_FWD + i,
                    )
            raise RuntimeError(
                f"All {self._max_slots} port slots are in use"
            )

    def release(self, slot_index: int) -> None:
        """Release a previously allocated port slot.

        Raises:
            ValueError: If the slot index was not allocated.
        """
        with self._lock:
            if slot_index not in self._used:
                raise ValueError(
                    f"Slot {slot_index} is not allocated"
                )
            self._used.discard(slot_index)
