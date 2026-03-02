#!/usr/bin/env bash
# Test that the debug keystore is valid and contains the expected key.
set -euo pipefail

KEYSTORE="android/keystores/debug.keystore"

if [ ! -f "$KEYSTORE" ]; then
  echo "FAIL: debug.keystore not found at $KEYSTORE" >&2
  exit 1
fi

# Verify keytool can read the keystore with the standard debug password
OUTPUT=$(keytool -list -keystore "$KEYSTORE" -storepass android 2>&1)

if ! echo "$OUTPUT" | grep -qi "androiddebugkey"; then
  echo "FAIL: expected alias 'androiddebugkey' not found in keystore" >&2
  echo "keytool output: $OUTPUT" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -qi "PrivateKeyEntry\|SecretKeyEntry\|trustedCertEntry\|keyEntry"; then
  echo "FAIL: no key entry found in keystore" >&2
  echo "keytool output: $OUTPUT" >&2
  exit 1
fi

echo "PASS: debug.keystore is valid with alias 'androiddebugkey'"
