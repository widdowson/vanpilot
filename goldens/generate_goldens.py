"""Regenerate golden images for VanPilot.

Usage: bazel run //goldens:generate_goldens
"""

import os
import sys

from mcp.src.png_util import make_teal_display


def main():
    # Resolve output directory relative to workspace root
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY", os.getcwd())
    phase3_dir = os.path.join(workspace, "goldens", "phase3")
    os.makedirs(phase3_dir, exist_ok=True)

    path = os.path.join(phase3_dir, "solid_color_surface.png")
    with open(path, "wb") as f:
        f.write(make_teal_display())
    print(f"Generated {path}")


if __name__ == "__main__":
    main()
