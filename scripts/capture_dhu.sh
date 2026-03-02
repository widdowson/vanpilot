#!/usr/bin/env bash
# Capture a screenshot of the Desktop Head Unit (DHU) window on macOS.
# Usage: scripts/capture_dhu.sh [output_path]
set -euo pipefail

OUTPUT="${1:-/tmp/dhu_screenshot.png}"

WID=$(swift -e '
import CoreGraphics
let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as! [[String: Any]]
for w in list {
    let owner = w["kCGWindowOwnerName"] as? String ?? ""
    let wid = w["kCGWindowNumber"] as? Int ?? 0
    let bounds = w["kCGWindowBounds"] as? [String: Any] ?? [:]
    let h = bounds["Height"] as? Int ?? 0
    if owner.lowercased().contains("desktop-head") && h > 100 {
        print(wid)
        break
    }
}
' 2>/dev/null)

if [ -z "$WID" ]; then
    echo "ERROR: DHU window not found" >&2
    exit 1
fi

screencapture -x -o -l "$WID" "$OUTPUT"
echo "$OUTPUT"
