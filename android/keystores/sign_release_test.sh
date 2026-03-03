#!/usr/bin/env bash
# Test that sign_release.sh validates required environment variables.
set -euo pipefail

SCRIPT="android/keystores/sign_release.sh"

if [ ! -x "$SCRIPT" ]; then
  echo "FAIL: sign_release.sh not found or not executable" >&2
  exit 1
fi

# Test 1: missing arguments should fail
if "$SCRIPT" 2>/dev/null; then
  echo "FAIL: expected non-zero exit with no arguments" >&2
  exit 1
fi
echo "PASS: rejects missing arguments"

# Test 2: missing env vars should fail
if "$SCRIPT" /dev/null /dev/null 2>/dev/null; then
  echo "FAIL: expected non-zero exit with no env vars set" >&2
  exit 1
fi
echo "PASS: rejects missing env vars"

# Test 3: missing keystore file should fail
export VANPILOT_RELEASE_KEYSTORE="/nonexistent/release.keystore"
export VANPILOT_RELEASE_KEYSTORE_PASS="testpass"
export VANPILOT_RELEASE_KEY_ALIAS="testkey"
export VANPILOT_RELEASE_KEY_PASS="testpass"
if "$SCRIPT" /dev/null /tmp/test-output.apk 2>/dev/null; then
  echo "FAIL: expected non-zero exit with missing keystore file" >&2
  exit 1
fi
echo "PASS: rejects missing keystore file"

echo "All sign_release.sh validation tests passed"
