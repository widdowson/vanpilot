# APK Deploy Recipe

How to build and install the VanPilot APK on an emulator instance managed by the instance manager.

## Prerequisites

- Instance manager running (`bazel run //instance_manager:instance_manager`)
- At least one running instance (created via `create` command)
- Bazel build environment configured

## Host Recipe (macOS)

### 1. Build the APK

```bash
bazel build //android:vanpilot
```

The debug APK is output at:
```
bazel-bin/android/vanpilot.apk
```

### 2. Install via Instance Manager CLI

```bash
# Install and restart DHU (default)
bazel run //instance_manager:instance_manager_client -- install-apk \
  --name my-instance \
  --apk bazel-bin/android/vanpilot.apk

# Install without restarting DHU
bazel run //instance_manager:instance_manager_client -- install-apk \
  --name my-instance \
  --apk bazel-bin/android/vanpilot.apk \
  --no-restart-dhu
```

### 3. Verify

```bash
# Take a screenshot to verify the app is running
bazel run //instance_manager:instance_manager_client -- screenshot \
  --name my-instance
```

## Sandbox Recipe (Docker agent)

From inside a Claude Code sandbox container with gRPC access to the instance manager:

### 1. Build the APK (requires Bazel fetch first)

```bash
# Ensure dependencies are fetched
bazel fetch //android:vanpilot

# Build
bazel build //android:vanpilot
```

### 2. Install via gRPC Client

```bash
python -c "
import grpc
from proto.vanpilot.v1 import instance_manager_pb2

channel = grpc.insecure_channel('host-machine:50061')
stub = channel.unary_unary(
    '/vanpilot.v1.InstanceManagerService/InstallApk',
    request_serializer=instance_manager_pb2.InstallApkRequest.SerializeToString,
    response_deserializer=instance_manager_pb2.InstallApkResponse.FromString,
)

with open('bazel-bin/android/vanpilot.apk', 'rb') as f:
    apk_data = f.read()

resp = stub(instance_manager_pb2.InstallApkRequest(
    name='my-instance',
    apk_data=apk_data,
    restart_dhu=True,
))
print(f'Installed on {resp.instance.name}, state={resp.instance.state}')
"
```

## Direct ADB Install (bypassing instance manager)

If you have direct ADB access:

```bash
# Find the emulator serial
adb devices

# Install
adb -s emulator-5554 install -r bazel-bin/android/vanpilot.apk
```

Note: After direct ADB install, you must manually restart the DHU for Android Auto to discover the updated app.

## Zero-Tap Auto-Launch Investigation

### Goal
Auto-launch VanPilot on the Android Auto head unit after APK install without manual interaction.

### Findings

1. **`am start-foreground-service`**: Android Auto CarAppService instances are managed by the Android Auto framework, not directly startable via `am start`. The service starts when Android Auto connects to it.

2. **Default navigation app**: VanPilot can be set as the default navigation app on the emulator:
   ```bash
   adb shell settings put secure default_navigation_app com.vanpilot.auto
   ```
   This causes Android Auto to auto-launch VanPilot when the DHU connects, which is the desired zero-tap behavior.

3. **After APK install + DHU restart**: The DHU restart triggers a fresh Android Auto connection. If VanPilot is set as the default navigation app, it auto-launches on the head unit display.

### Recommended Approach

Set `default_navigation_app` in the emulator snapshot (`aa_ready`) so every instance boots with VanPilot auto-launching. This is a one-time setup:

```bash
adb shell settings put secure default_navigation_app com.vanpilot.auto
# Then save a new snapshot
```

After this, the `InstallApk` RPC with `restart_dhu=True` provides true zero-tap deploy: build APK, install, DHU restarts, VanPilot auto-launches.
