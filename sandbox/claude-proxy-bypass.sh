#!/bin/bash
# Project-specific proxy bypasses for VanPilot

# Instance manager gRPC (Tailscale hostname)
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "mac"

# Package registry CONNECT passthrough
#
# The sandbox MITM proxy intercepts HTTPS traffic by default, which breaks
# hermetic pip (chunked encoding timeouts) and can cause TLS issues with
# package managers. These hosts are trusted package registries that don't
# need content inspection — using CONNECT passthrough lets clients see
# real TLS certificates directly, avoiding MITM-related failures.
#
# Note: github.com is already bypassed in claude.sh, so it's not listed here.
BYPASS_HOSTS=(
    # Python packages
    pypi.org
    files.pythonhosted.org
    # Maven / Android dependencies
    maven.google.com
    repo1.maven.org
    # Bazel registries and mirrors
    bcr.bazel.build
    mirror.bazel.build
    # GitHub content (release assets, raw files)
    objects.githubusercontent.com
    raw.githubusercontent.com
)

for host in "${BYPASS_HOSTS[@]}"; do
    docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "$host"
done
