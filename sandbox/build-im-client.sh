#!/bin/bash
# Builds the instance manager client zip and copies it to sandbox/ for Docker image builds.
# Run this from the repo root before building the sandbox Docker image.
set -euo pipefail

bazel build //instance_manager:instance_manager_client_zip
cp bazel-bin/instance_manager/instance_manager_client.zip sandbox/
echo "instance_manager_client.zip copied to sandbox/"
