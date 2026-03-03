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
bazel run //instance_manager:instance_manager_client --
```

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

Connect with:

```bash
adb -s emulator-5554 shell
```

The serial is always `emulator-{console_port}`. Common operations:

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

### Typical workflow: launch app and interact

```bash
# 1. Create instance
im create --name test-1

# 2. Go to home screen
im dhu-command --name test-1 keycode home

# 3. Open the app launcher (bottom-left grid icon)
im dhu-command --name test-1 --screenshot tap 27 515

# 4. Tap your app
im dhu-command --name test-1 --screenshot tap 300 200

# 5. Interact with your app's UI
im dhu-command --name test-1 --screenshot tap 480 300

# 6. When done, tear down
im destroy --name test-1
```

## Restarting the DHU

After installing or updating an APK, Android Auto needs to rediscover the app. Restart the DHU (the emulator stays running):

```bash
adb -s emulator-5554 install my-app.apk
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
```

Use `grpc.insecure_channel("localhost:50061")` to connect. See `instance_manager/src/client.py` for a working example of building stubs without codegen.
