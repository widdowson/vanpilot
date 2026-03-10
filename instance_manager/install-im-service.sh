#!/usr/bin/env bash
# Install or uninstall the VanPilot Instance Manager launchd service.
#
# Usage:
#   ./instance_manager/install-im-service.sh              # install & start
#   ./instance_manager/install-im-service.sh --uninstall  # stop & remove
#   ./instance_manager/install-im-service.sh --status     # show service status
set -euo pipefail

LABEL="photos.apw.vanpilot.instance-manager"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
VANPILOT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IM_ZIP_SRC="$VANPILOT_ROOT/bazel-bin/instance_manager/instance_manager.zip"
INSTALL_DIR="$HOME/Library/Application Support/VanPilot"
IM_ZIP_DST="$INSTALL_DIR/instance_manager.zip"

status() {
    if launchctl list "$LABEL" &>/dev/null; then
        echo "Service is loaded."
        launchctl list "$LABEL"
    else
        echo "Service is not loaded."
    fi
}

uninstall() {
    echo "Stopping and unloading ${LABEL}..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "Uninstalled. (Binary left at $IM_ZIP_DST — remove manually if desired.)"
}

install() {
    if [ ! -f "$IM_ZIP_SRC" ]; then
        echo "ERROR: Instance manager zip not found at:" >&2
        echo "  $IM_ZIP_SRC" >&2
        echo "" >&2
        echo "Build it first with:" >&2
        echo "  cd $VANPILOT_ROOT && bazel build //instance_manager:instance_manager_zip" >&2
        exit 1
    fi

    # Copy zip outside the git/bazel tree so bazel clean won't delete it
    mkdir -p "$INSTALL_DIR"
    # Bazel outputs are read-only; ensure the destination is writable for future upgrades
    rm -f "$IM_ZIP_DST"
    cp "$IM_ZIP_SRC" "$IM_ZIP_DST"
    chmod u+w "$IM_ZIP_DST"
    echo "Copied instance_manager.zip to $IM_ZIP_DST"

    # Ensure log directory exists
    mkdir -p "$HOME/Library/Logs"

    # Unload existing service if present
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

    # Generate plist with resolved paths
    sed \
        -e "s|__INSTANCE_MANAGER_ZIP__|${IM_ZIP_DST}|g" \
        -e "s|__VANPILOT_ROOT__|${VANPILOT_ROOT}|g" \
        -e "s|__HOME__|${HOME}|g" \
        "$PLIST_SRC" > "$PLIST_DST"

    echo "Installed plist to $PLIST_DST"

    # Load and start
    launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
    echo "Service loaded. Checking status..."
    sleep 1
    status

    echo ""
    echo "Logs: tail -f ~/Library/Logs/vanpilot-im.log"
}

case "${1:-}" in
    --uninstall) uninstall ;;
    --status)    status ;;
    *)           install ;;
esac
