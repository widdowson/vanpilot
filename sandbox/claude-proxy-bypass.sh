#!/bin/bash
# Project-specific proxy bypasses for VanPilot
docker sandbox network proxy "$SANDBOX_NAME" --bypass-host "mac"
