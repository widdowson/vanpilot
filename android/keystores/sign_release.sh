#!/usr/bin/env bash
# Sign an APK with the release keystore.
#
# Required environment variables:
#   VANPILOT_RELEASE_KEYSTORE      — path to the release .keystore file
#   VANPILOT_RELEASE_KEYSTORE_PASS — keystore password
#   VANPILOT_RELEASE_KEY_ALIAS     — key alias within the keystore
#   VANPILOT_RELEASE_KEY_PASS      — key password
#
# Usage:
#   ./android/keystores/sign_release.sh <unsigned-apk> <output-apk>

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <unsigned-apk> <output-apk>" >&2
  exit 1
fi

UNSIGNED_APK="$1"
OUTPUT_APK="$2"

# Validate required environment variables
for var in VANPILOT_RELEASE_KEYSTORE VANPILOT_RELEASE_KEYSTORE_PASS \
           VANPILOT_RELEASE_KEY_ALIAS VANPILOT_RELEASE_KEY_PASS; do
  if [ -z "${!var:-}" ]; then
    echo "Error: $var is not set" >&2
    exit 1
  fi
done

if [ ! -f "$VANPILOT_RELEASE_KEYSTORE" ]; then
  echo "Error: keystore not found at $VANPILOT_RELEASE_KEYSTORE" >&2
  exit 1
fi

if [ ! -f "$UNSIGNED_APK" ]; then
  echo "Error: unsigned APK not found at $UNSIGNED_APK" >&2
  exit 1
fi

if ! command -v apksigner &>/dev/null; then
  echo "Error: apksigner not found on \$PATH." >&2
  echo "Install it via the Android SDK Build-Tools:" >&2
  echo "  sdkmanager 'build-tools;<version>'" >&2
  echo "Then ensure \$ANDROID_HOME/build-tools/<version> is on your PATH." >&2
  exit 1
fi

# Copy the unsigned APK to the output path for in-place signing
cp "$UNSIGNED_APK" "$OUTPUT_APK"

# Sign with apksigner
apksigner sign \
  --ks "$VANPILOT_RELEASE_KEYSTORE" \
  --ks-pass "pass:$VANPILOT_RELEASE_KEYSTORE_PASS" \
  --ks-key-alias "$VANPILOT_RELEASE_KEY_ALIAS" \
  --key-pass "pass:$VANPILOT_RELEASE_KEY_PASS" \
  "$OUTPUT_APK"

echo "Signed APK: $OUTPUT_APK"
