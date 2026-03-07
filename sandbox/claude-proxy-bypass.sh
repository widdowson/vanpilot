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

# Python packages
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "pypi.org"
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "files.pythonhosted.org"

# Maven / Android dependencies
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "maven.google.com"
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "repo1.maven.org"

# Bazel registries and mirrors
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "bcr.bazel.build"
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "mirror.bazel.build"

# GitHub content (release assets, raw files)
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "objects.githubusercontent.com"
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "raw.githubusercontent.com"
