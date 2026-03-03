#!/bin/bash
#
# Project-specific runtime init for the VanPilot sandbox.
# Called by claude.sh after sandbox-init.sh (which installs the proxy CA cert).
#
# Imports the proxy CA into JDK and Bazel truststores so that:
#   - Bazel's host JVM can fetch from BCR (bazel_skylib, rules_android, etc.)
#   - Coursier/rules_jvm_external can fetch Maven dependencies
#
# This MUST run at sandbox start, not at Docker image build time, because the
# proxy CA cert is injected by the sandbox infrastructure after container creation.
#
set -euo pipefail

PROXY_CA="/usr/local/share/ca-certificates/proxy-ca.crt"
BAZEL_TRUSTSTORE="/home/agent/.bazel-ssl/cacerts"

if [[ ! -f "$PROXY_CA" ]]; then
  echo "project-init: No proxy CA found — skipping truststore setup."
  exit 0
fi

# --- Bazel host JVM truststore ---
# bazelrc.sandbox startup option references this path.
if [[ -f "$BAZEL_TRUSTSTORE" ]] && keytool -list -keystore "$BAZEL_TRUSTSTORE" -storepass changeit -alias proxy-ca >/dev/null 2>&1; then
  echo "project-init: Bazel truststore already has proxy CA."
else
  echo "project-init: Creating Bazel truststore with proxy CA..."
  JDK_CACERTS=$(find /usr/lib/jvm -name cacerts -print -quit 2>/dev/null || true)
  if [[ -z "$JDK_CACERTS" ]]; then
    echo "project-init: ERROR — no JDK cacerts found under /usr/lib/jvm" >&2
    exit 1
  fi
  cp "$JDK_CACERTS" "$BAZEL_TRUSTSTORE"
  keytool -importcert -noprompt -trustcacerts -alias proxy-ca \
    -file "$PROXY_CA" -keystore "$BAZEL_TRUSTSTORE" -storepass changeit
  echo "project-init: Bazel truststore created at $BAZEL_TRUSTSTORE"
fi

# --- JDK truststores (for Coursier/Maven) ---
for ks in $(find /usr/lib/jvm -name cacerts 2>/dev/null); do
  if keytool -list -keystore "$ks" -storepass changeit -alias proxy-ca >/dev/null 2>&1; then
    echo "project-init: JDK truststore $ks already has proxy CA."
  else
    echo "project-init: Importing proxy CA into $ks..."
    sudo keytool -importcert -noprompt -trustcacerts -alias proxy-ca \
      -file "$PROXY_CA" -keystore "$ks" -storepass changeit
  fi
done

echo "project-init: Done."
