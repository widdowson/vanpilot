"""Coordinate calibration for DHU screenshot-to-tap mapping.

Agents see DHU screenshots (1920x1080) but the VanPilot app occupies only a
portion of the display. This module generates a calibration pattern, detects
it in a screenshot, and computes the coordinate transform.

Pillow (PIL) is imported lazily inside functions to avoid breaking transitive
importers when Pillow is not available in the Bazel hermetic Python toolchain.
"""

import io

# Marker size in pixels
MARKER_SIZE = 50

# Calibration colors
MAGENTA = (255, 0, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# Color distance threshold for marker detection
_COLOR_THRESHOLD = 80


def generate_calibration_pattern(width: int, height: int) -> bytes:
    """Generate a calibration pattern PNG.

    Creates an image with magenta background and four colored corner markers
    (each 50x50px): red top-left, green top-right, blue bottom-left, yellow
    bottom-right.

    Args:
        width: Pattern width in pixels.
        height: Pattern height in pixels.

    Returns:
        Raw PNG bytes.
    """
    from PIL import Image

    img = Image.new("RGB", (width, height), MAGENTA)

    # Draw corner markers
    _fill_rect(img, 0, 0, MARKER_SIZE, MARKER_SIZE, RED)
    _fill_rect(img, width - MARKER_SIZE, 0, MARKER_SIZE, MARKER_SIZE, GREEN)
    _fill_rect(img, 0, height - MARKER_SIZE, MARKER_SIZE, MARKER_SIZE, BLUE)
    _fill_rect(img, width - MARKER_SIZE, height - MARKER_SIZE, MARKER_SIZE, MARKER_SIZE, YELLOW)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def detect_calibration_markers(screenshot_png: bytes) -> dict:
    """Detect calibration markers in a DHU screenshot.

    Scans the screenshot for clusters of the four marker colors and returns
    their center positions.

    Args:
        screenshot_png: Full DHU screenshot as PNG bytes (typically 1920x1080).

    Returns:
        Dict with marker center positions:
        {"red_tl": (x, y), "green_tr": (x, y),
         "blue_bl": (x, y), "yellow_br": (x, y)}
    """
    from PIL import Image

    img = Image.open(io.BytesIO(screenshot_png)).convert("RGB")

    markers = {
        "red_tl": _find_marker_center(img, RED),
        "green_tr": _find_marker_center(img, GREEN),
        "blue_bl": _find_marker_center(img, BLUE),
        "yellow_br": _find_marker_center(img, YELLOW),
    }
    return markers


def compute_transform(markers: dict, pattern_size: tuple) -> dict:
    """Compute the coordinate transform from app coordinates to DHU coordinates.

    Args:
        markers: Detected marker positions from detect_calibration_markers().
        pattern_size: (width, height) of the original calibration pattern.

    Returns:
        Dict with transform parameters:
        - app_rect: {left, top, right, bottom} of the app area in screenshot coords
        - scale_x, scale_y: scale factors from pattern coords to screenshot coords
        - offset_x, offset_y: offset of app area in screenshot
        - usage: human-readable formula
    """
    pat_w, pat_h = pattern_size

    # Marker centers are at (25, 25) from each corner in pattern coords.
    # In screenshot coords, the markers tell us where those points are.
    # So the app area extends 25 pixels beyond each marker center.
    half_marker = MARKER_SIZE // 2

    tl = markers["red_tl"]
    tr = markers["green_tr"]
    bl = markers["blue_bl"]
    br = markers["yellow_br"]

    # App rectangle in screenshot coordinates
    left = round((tl[0] + bl[0]) / 2 - half_marker)
    top = round((tl[1] + tr[1]) / 2 - half_marker)
    right = round((tr[0] + br[0]) / 2 + half_marker)
    bottom = round((bl[1] + br[1]) / 2 + half_marker)

    # Displayed size in screenshot pixels
    disp_w = right - left
    disp_h = bottom - top

    # Scale: how many screenshot pixels per pattern pixel
    scale_x = disp_w / pat_w
    scale_y = disp_h / pat_h

    return {
        "app_rect": {"left": left, "top": top, "right": right, "bottom": bottom},
        "scale_x": round(scale_x, 4),
        "scale_y": round(scale_y, 4),
        "offset_x": left,
        "offset_y": top,
        "usage": "dhu_x = offset_x + app_x * scale_x",
    }


def _fill_rect(
    img, x: int, y: int, w: int, h: int, color: tuple
) -> None:
    """Fill a rectangle in the image."""
    for py in range(y, y + h):
        for px in range(x, x + w):
            img.putpixel((px, py), color)


def _color_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance between two RGB colors."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def _find_marker_center(img, target_color: tuple) -> tuple:
    """Find the center of a marker region by scanning for matching pixels.

    Uses a sampling strategy for performance: scan every 2nd pixel to find
    the bounding box, then compute the center.
    """
    w, h = img.size
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    found = False

    step = 2
    for py in range(0, h, step):
        for px in range(0, w, step):
            pixel = img.getpixel((px, py))
            if _color_distance(pixel, target_color) < _COLOR_THRESHOLD:
                if px < min_x:
                    min_x = px
                if px > max_x:
                    max_x = px
                if py < min_y:
                    min_y = py
                if py > max_y:
                    max_y = py
                found = True

    if not found:
        raise ValueError(f"Marker color {target_color} not found in screenshot")

    cx = (min_x + max_x) // 2
    cy = (min_y + max_y) // 2
    return (cx, cy)
