#!/bin/bash
# Pre-build hook: build artifacts required by the sandbox Dockerfile.
# Runs automatically before Docker image build via claude.sh.

echo "Building instance manager client zip..."
bash "$PROJECT_DIR/sandbox/build-im-client.sh"
