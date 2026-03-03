"""Display profiles for golden test infrastructure (AC-10.2).

Defines named display profiles that configure the DHU (Desktop Head Unit)
resolution and golden image directory for different target displays.

Profiles:
  - default: 800x480, the standard DHU resolution (phase9 goldens)
  - 13inch:  1920x720, 13-inch automotive ultrawide display (AC-10.2)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayProfile:
    """Configuration for a target display."""

    name: str
    dhu_width: int
    dhu_height: int
    dhu_dpi: int
    golden_subdir: str

    @property
    def dhu_resolution_arg(self) -> str:
        """DHU --resolution argument value (WxH)."""
        return f"{self.dhu_width}x{self.dhu_height}"


_PROFILES: dict[str, DisplayProfile] = {
    "default": DisplayProfile(
        name="default",
        dhu_width=800,
        dhu_height=480,
        dhu_dpi=160,
        golden_subdir="phase9",
    ),
    "13inch": DisplayProfile(
        name="13inch",
        dhu_width=1920,
        dhu_height=720,
        dhu_dpi=160,
        golden_subdir="13inch",
    ),
}


def get_profile(name: str) -> DisplayProfile:
    """Look up a display profile by name.

    Raises:
        KeyError: If the profile name is not recognized.
    """
    return _PROFILES[name]


def list_profiles() -> list[str]:
    """Return all registered profile names."""
    return list(_PROFILES.keys())
