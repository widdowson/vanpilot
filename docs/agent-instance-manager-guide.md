# Agent Guide: Using the Instance Manager

How to create, control, and tear down emulator + Android Auto DHU instances from an agent sandbox.

## Prerequisites

The instance manager server must be running on the Mac Studio:

```bash
bazel run //instance_manager:instance_manager
# → Instance manager gRPC on :50061, HTTP dashboard on :8080
```

All commands below use the CLI client. The shorthand `im` means:

```bash
# Inside a Docker sandbox (preferred — pre-built, no Bazel needed):
im

# On the host (builds from source):
bazel run //instance_manager:instance_manager_client --
```

Inside Docker sandboxes, the `im` command is pre-installed at `/usr/local/bin/im`. It runs the pre-built instance manager client zip without needing Bazel. This avoids pip timeout issues through the MITM proxy.

If the server is on a different host (e.g. you're in a Docker sandbox talking over Tailscale), pass `--addr <host>:50061`.

## Quick Reference

| Command | What it does |
|---|---|
| `im create --name my-emu` | Start emulator + DHU pair |
| `im destroy --name my-emu` | Stop and clean up |
| `im list` | Show all instances and their states |
| `im get --name my-emu` | Details for one instance |
| `im screenshot --name my-emu` | Capture DHU + phone screenshots |
| `im dhu-command --name my-emu keycode home` | Send DHU console command |
| `im dhu-command --name my-emu --screenshot tap 300 430` | Send command + capture screenshot |
| `im restart-dhu --name my-emu` | Restart DHU without killing emulator |
| `im install-apk --name my-emu --apk app.apk` | Install APK + restart DHU |
| `im launch-app --name my-emu` | Launch VanPilot on the DHU |
| `im adb --name my-emu pm list packages` | Run adb shell command via gRPC |
| `im adb-push --name my-emu --file f --remote /path` | Push file to emulator via gRPC |
| `im adb-pull --name my-emu --remote /path` | Pull file from emulator via gRPC |

## Instance Lifecycle

### Create an instance

```bash
im create --name coder-1
```

This boots the emulator from the `aa_ready` snapshot, starts the DHU, waits for the SSL handshake and video focus, then captures initial screenshots. Takes ~30s.

Output:
```
Creating instance 'coder-1'...
OK
  coder-1  state=RUNNING  console=5554  adb=5555  aa=5277  headful=False  avd=vanpilot_pixel9pro_api36
    DHU screenshot: 20080 bytes
    Phone screenshot: 221666 bytes
```

Options:
- `--headful` — show the emulator GUI window (default: headless)
- `--avd <name>` — use a different AVD (default: `vanpilot_pixel9pro_api36`)
- `--snapshot <name>` — boot from a different snapshot (default: `aa_ready`)
- `--timeout <seconds>` — creation timeout (default: 180)

### List instances

```bash
im list
```

Shows all instances with their state, ports, and screenshot sizes.

### Destroy an instance

```bash
im destroy --name coder-1
```

Kills the DHU and emulator processes, removes port forwards, and cleans up temp files. The name becomes available for reuse.

## Connecting to ADB

Each instance gets its own ADB port. The `create` output shows it:

```
console=5554  adb=5555
```

### Local access (on the Mac Studio)

Connect with:

```bash
adb -s emulator-5554 shell
```

The serial is always `emulator-{console_port}`.

### Remote access (from a Docker sandbox)

The ADB port is exposed on all network interfaces via a `socat` forwarder, so sandbox agents can connect over Tailscale:

```bash
adb connect mac:5555
adb -s mac:5555 shell
```

Replace `mac` with the Tailscale hostname or IP of the Mac Studio. The port is the ADB port shown in the `create` output.

### Common operations (via gRPC — preferred for sandbox agents)

The `adb`, `adb-push`, and `adb-pull` commands proxy ADB operations through gRPC, so sandbox agents don't need a direct ADB connection:

```bash
# Install an APK (restarts DHU automatically)
im install-apk --name coder-1 --apk /path/to/app.apk

# Run a shell command
im adb --name coder-1 pm list packages

# View logcat
im adb --name coder-1 logcat -d -s VanPilot:*

# Push a file (max ~4MB due to gRPC message size limit)
im adb-push --name coder-1 --file local.txt --remote /sdcard/local.txt

# Pull a file
im adb-pull --name coder-1 --remote /sdcard/file.txt --output file.txt
```

### Common operations (via direct ADB — on the Mac Studio)

```bash
# Install an APK
adb -s emulator-5554 install /path/to/app.apk

# After installing, restart the DHU so Android Auto discovers the new app
im restart-dhu --name coder-1

# Push a file
adb -s emulator-5554 push local.txt /sdcard/

# Run a shell command
adb -s emulator-5554 shell pm list packages | grep vanpilot

# View logcat
adb -s emulator-5554 logcat -d -s VanPilot:*
```

Port allocation for multiple instances:

| Instance | Console | ADB | AA Forward |
|---|---|---|---|
| 1st | 5554 | 5555 | 5277 |
| 2nd | 5556 | 5557 | 5278 |
| 3rd | 5558 | 5559 | 5279 |
| ... | +2 | +2 | +1 |

Up to 8 concurrent instances.

## Screenshots

### Capture both DHU and phone screens

```bash
im screenshot --name coder-1
```

Saves to `/tmp/coder-1_dhu.png` and `/tmp/coder-1_phone.png` by default.

```bash
# Custom output paths
im screenshot --name coder-1 --output /tmp/dhu.png --emu-output /tmp/phone.png
```

The **DHU screenshot** shows what the driver sees on the Android Auto head unit display (1920x1080). The **phone screenshot** shows the emulator's own screen via `adb screencap` — useful for seeing notifications, settings, or apps not projected to AA.

### Screenshots via the web dashboard

The instance manager also serves a live dashboard at `http://localhost:8080` with auto-refreshing thumbnails (every 30s). Useful for quick visual checks without the CLI. Direct image URLs:

```
http://localhost:8080/instances/coder-1/dhu-screenshot
http://localhost:8080/instances/coder-1/emu-screenshot
```

## DHU Commands

The DHU console accepts commands for input simulation, display modes, and sensors. Send them with `dhu-command`:

```bash
# No screenshot — just send the command
im dhu-command --name coder-1 keycode home

# Send command + capture screenshot after 1s settle delay
im dhu-command --name coder-1 --screenshot tap 300 430

# Save screenshot to a specific path
im dhu-command --name coder-1 --screenshot --output /tmp/after-tap.png tap 300 430
```

When `--screenshot` is used, the captured image also updates the web dashboard cache immediately (no need to wait for the 30s refresh cycle).

### Common DHU commands

**Navigation and input:**

| Command | Description |
|---|---|
| `tap <x> <y>` | Tap at pixel coordinates (1920x1080 display) |
| `keycode home` | Press the home button |
| `keycode back` | Press the back button |
| `keycode dpad_up` | D-pad up |
| `keycode dpad_down` | D-pad down |
| `keycode dpad_left` | D-pad left |
| `keycode dpad_right` | D-pad right |
| `keycode dpad_center` | D-pad select/enter |
| `keycode media_play_pause` | Toggle media playback |
| `keycode search` | Voice search button |

**Display modes:**

| Command | Description |
|---|---|
| `day` | Switch to day mode (light theme) |
| `night` | Switch to night mode (dark theme) |

**Rotary input (for knob-based head units):**

| Command | Description |
|---|---|
| `rotate left` | Rotate knob left |
| `rotate right` | Rotate knob right |

### Full workflow: build, install, launch VanPilot

```bash
# 1. Create instance (boots from aa_ready snapshot — VanPilot NOT pre-installed)
im create --name test-1

# 2. Build the APK
bazel build //android:vanpilot

# 3. Install APK (restarts DHU so Android Auto discovers the new app)
im install-apk --name test-1 --apk bazel-bin/android/vanpilot.apk

# 4. Launch VanPilot (opens launcher, taps VanPilot icon)
im launch-app --name test-1 --screenshot

# 5. Interact with VanPilot's UI
im dhu-command --name test-1 --screenshot tap 480 300

# 6. When done, tear down
im destroy --name test-1
```

The `launch-app` command:
1. Sends `keycode home` to open the app launcher grid
2. Waits 2 seconds for the launcher to render
3. Taps VanPilot's icon at (200, 390) in the 1920x1080 coordinate system
4. Waits for app initialization

Override the tap coordinates with `--x` and `--y` if the grid layout changes. See `docs/app-launch.md` for the full launcher grid coordinate map and troubleshooting.

## APK Installation

The `aa_ready` snapshot does NOT have VanPilot pre-installed. Install the APK after creating an instance:

```bash
# Install APK + restart DHU in one command
im install-apk --name coder-1 --apk vanpilot.apk

# Or install without restarting DHU
im install-apk --name coder-1 --apk vanpilot.apk --no-restart-dhu
```

The `install-apk` command:
1. Pushes the APK to the emulator via `adb install`
2. Restarts the DHU (by default) so Android Auto discovers the new app
3. Returns the updated instance info with fresh screenshots

## Restarting the DHU

If you need to restart the DHU independently (e.g., after changing Android Auto settings):

```bash
im restart-dhu --name coder-1
```

This kills the old DHU, spawns a fresh one, waits for the SSL handshake + video focus, and captures new screenshots. Takes ~15s.

## Error Handling

The CLI prints gRPC errors to stderr:

```
ERROR: StatusCode.NOT_FOUND — Instance 'nope' not found
ERROR: StatusCode.FAILED_PRECONDITION — Instance 'x' is not running (state=1)
ERROR: StatusCode.ALREADY_EXISTS — Instance 'dup' already exists
ERROR: StatusCode.INVALID_ARGUMENT — Invalid name '../../bad': must match [a-zA-Z0-9][a-zA-Z0-9._-]*
```

Instance names must match `[a-zA-Z0-9][a-zA-Z0-9._-]*` (letters, digits, dots, hyphens, underscores; must start with alphanumeric).

### Snapshot sentinel file

The `aa_ready` snapshot contains a sentinel file at `/data/local/tmp/.vanpilot_snapshot_sentinel`. During instance creation, after the emulator reports `sys.boot_completed=1`, the instance manager checks for this file:

```bash
adb -s emulator-<console_port> shell ls /data/local/tmp/.vanpilot_snapshot_sentinel
```

If the file is missing, the emulator cold-booted instead of resuming the snapshot (e.g. due to a GPU renderer mismatch). The instance is set to ERROR state with the message:

```
Snapshot sentinel missing on emulator-5554: emulator cold-booted instead of resuming snapshot. Check -gpu flag and AVD snapshot name.
```

**What to do when you see this error:**

1. Check that the `-gpu` flag matches the renderer used when the snapshot was saved. The instance manager auto-detects this from `snapshot.pb`, but a corrupted or missing snapshot metadata file can cause a mismatch.
2. Verify the snapshot name exists in the AVD's `snapshots/` directory.
3. Check the emulator log at `/tmp/emu_<name>.log` for renderer errors.

The sentinel check is skipped when no snapshot is specified (empty `snapshot_name`), since cold boot is the expected behavior in that case.

## gRPC API

For agents that want to call the gRPC API directly (e.g. from Python) instead of shelling out to the CLI, the service is defined in `proto/vanpilot/v1/instance_manager.proto`:

```
vanpilot.v1.InstanceManagerService on port 50061

CreateInstance(name, headful?, avd_name?, snapshot_name?) → InstanceInfo
DestroyInstance(name) → {}
ListInstances() → [InstanceInfo]
GetInstance(name) → InstanceInfo
ScreenshotInstance(name) → {dhu_screenshot_png, emulator_screenshot_png, captured_at_ms}
RestartDhu(name) → InstanceInfo
DhuCommand(name, command, capture_screenshot?) → {executed_at_ms, screenshot_png}
InstallApk(name, apk_data, restart_dhu?) → InstanceInfo
AdbShell(name, args[], timeout_s?) → {exit_code, stdout, stderr}
AdbPush(name, data, remote_path) → {}
AdbPull(name, remote_path) → {data}
StartVideoCapture(name, target_fps?, max_duration_s?) → {capture_id}
StopVideoCapture(name) → {video_mp4, frame_count, actual_fps, duration_ms, capture_id}
```

Use `grpc.insecure_channel("mac:50061")` to connect. See `instance_manager/src/client.py` for a working example of building stubs without codegen.
