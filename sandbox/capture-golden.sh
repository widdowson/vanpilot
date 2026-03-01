#!/usr/bin/env bash
# Capture an authentic Android Auto golden screenshot via sidecar.
#
# Uses the emulator SIDECAR approach (no KVM required):
#   docker run --platform linux/amd64 -d --name vanpilot-emu -p 5555:5555 vanpilot-emu
#
# Usage: ./sandbox/capture-golden.sh [output.png]

set -euo pipefail

OUTPUT="${1:-goldens/phase9/android_auto_screenshot.png}"
EMU_HOST="${EMU_HOST:-localhost}"
EMU_PORT="${EMU_PORT:-5555}"
EMU_ADDR="${EMU_HOST}:${EMU_PORT}"
TIMEOUT_BOOT=300

cleanup() { adb disconnect "${EMU_ADDR}" 2>/dev/null || true; }
trap cleanup EXIT

adb connect "${EMU_ADDR}"

echo "Waiting for emulator to boot (up to ${TIMEOUT_BOOT}s)..."
DEADLINE=$((SECONDS + TIMEOUT_BOOT))
while [[ $SECONDS -lt $DEADLINE ]]; do
    BOOT=$(adb -s "${EMU_ADDR}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
    [[ "$BOOT" == "1" ]] && break
    sleep 5
done
[[ "$(adb -s "${EMU_ADDR}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]] || { echo "ERROR: Boot timeout"; exit 1; }

APK_PATH="bazel-bin/android/vanpilot.apk"
if [[ ! -f "${APK_PATH}" ]]; then
    echo "APK not found at ${APK_PATH}, building..."
    bazel build //android:vanpilot
fi
[[ -f "${APK_PATH}" ]] || { echo "ERROR: APK not found at ${APK_PATH} after build"; exit 1; }
echo "Installing ${APK_PATH}..."
adb -s "${EMU_ADDR}" install -r "${APK_PATH}"
sleep 15

mkdir -p "$(dirname "${OUTPUT}")"
adb -s "${EMU_ADDR}" shell screencap -p /sdcard/golden.png
adb -s "${EMU_ADDR}" pull /sdcard/golden.png "${OUTPUT}"
adb -s "${EMU_ADDR}" shell rm /sdcard/golden.png

echo "Golden: ${OUTPUT} ($(wc -c < "${OUTPUT}") bytes)"
