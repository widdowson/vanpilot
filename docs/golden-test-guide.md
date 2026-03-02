# Golden Test Infrastructure Usage Guide

This guide explains how to run, create, and update golden screenshot tests for VanPilot on a macOS host.

## Overview

Golden tests capture screenshots of the VanPilot Android Auto UI and compare them pixel-by-pixel against committed reference images (goldens). The project owner reviews PRs primarily by examining golden image diffs, so keeping goldens accurate and up to date is critical.

**Key components:**

| File | Purpose |
|---|---|
| `goldens/golden_diff.py` | Pixel-by-pixel PNG comparison with diff image generation |
| `goldens/capture_emulator.py` | Automated screenshot capture from Android emulator via ADB |
| `goldens/generate_goldens.py` | Regenerates synthetic goldens (e.g., solid color surfaces) |
| `goldens/test_emulator_golden.py` | Emulator-based golden test (Bazel `manual` tag) |
| `goldens/video_capture.py` | Optional video capture of last N seconds before golden frame |
| `scripts/dhu.sh` | Desktop Head Unit (DHU) lifecycle management |
| `scripts/capture_dhu.sh` | macOS-native DHU window screenshot capture |

Golden images are committed under `goldens/` in phase-specific subdirectories (e.g., `goldens/phase3/`, `goldens/phase9/`).

## Prerequisites

### Android SDK & Platform Tools

Install via Android Studio or the command-line tools:

```bash
# If using Android Studio, SDK is typically at:
# ~/Library/Android/sdk

# Ensure platform-tools (adb) and the target API are installed:
sdkmanager "platform-tools" "platforms;android-34"

# Verify adb is on your PATH:
adb version
```

### Android Emulator AVD

Create an AVD for the target device. VanPilot targets the Pixel 10 Pro form factor:

```bash
# Install emulator and a system image:
sdkmanager "emulator" "system-images;android-34;google_apis;arm64-v8a"

# Create an AVD:
avdmanager create avd -n vanpilot_test -k "system-images;android-34;google_apis;arm64-v8a"

# Start the emulator:
emulator -avd vanpilot_test
```

The emulator appears as `emulator-5554` (or similar) in `adb devices`.

### Desktop Head Unit (DHU)

The DHU simulates the Android Auto head unit display. Install it via Android Studio's SDK Manager:

1. Open Android Studio > SDK Manager > SDK Tools tab
2. Check "Android Auto Desktop Head Unit Emulator"
3. Install

The DHU binary is at `$ANDROID_HOME/extras/google/auto/desktop-head-unit`.

### Bazel

VanPilot uses Bazel as its sole build system. Install via Bazelisk:

```bash
brew install bazelisk
```

### Build the APK

```bash
bazel build //android:vanpilot
# Output: bazel-bin/android/vanpilot.apk
```

## Running Existing Golden Tests

### Unit-level golden tests (no emulator needed)

These tests compare pre-generated images against committed goldens. They run as part of the standard test suite:

```bash
# Run all non-manual golden tests:
bazel test //goldens:solid_color_surface_test
bazel test //goldens:golden_diff_test

# Or run everything (these are included in //...):
bazel test //...
```

### Emulator-based golden test

The emulator golden test (`emulator_golden_test`) is tagged `manual` and `exclusive` — it does **not** run during `bazel test //...`. It requires a running Android emulator.

**Step 1: Start the emulator**

```bash
emulator -avd vanpilot_test &
# Wait for it to boot:
adb wait-for-device
adb shell getprop sys.boot_completed  # Returns "1" when ready
```

**Step 2: Start the DHU**

```bash
# Forward the Android Auto port:
adb forward tcp:5277 tcp:5277

# Start DHU (using the helper script):
scripts/dhu.sh start

# Or manually:
$ANDROID_HOME/extras/google/auto/desktop-head-unit
```

**Step 3: Build and install the APK**

```bash
bazel build //android:vanpilot
adb install -r bazel-bin/android/vanpilot.apk
```

**Step 4: Run the test**

```bash
# Native emulator (auto-detected via adb devices):
bazel test //goldens:emulator_golden_test

# Or with explicit TCP connection:
bazel test //goldens:emulator_golden_test \
  --test_env=EMU_HOST=localhost \
  --test_env=EMU_PORT=5555
```

The test:
1. Discovers the emulator (native ADB or TCP)
2. Captures a screenshot via `adb screencap`
3. Compares it against `goldens/phase9/emulator_screenshot.png`
4. On mismatch, saves `diff.png` to `TEST_UNDECLARED_OUTPUTS_DIR`

**Step 5: View test outputs on failure**

```bash
# Bazel puts undeclared outputs under:
# bazel-testlogs/goldens/emulator_golden_test/test.outputs/
ls bazel-testlogs/goldens/emulator_golden_test/test.outputs/
# Files: actual.png, golden.png, diff.png
```

The diff image highlights changed pixels in red with unchanged pixels dimmed.

## Capturing New Golden Screenshots

### Method 1: Using `capture_emulator.py` (recommended)

This script handles the full workflow: connect to emulator, optionally install APK, launch the app, wait for rendering to settle, and capture.

```bash
# With a native emulator already running:
python goldens/capture_emulator.py \
  --native \
  --apk bazel-bin/android/vanpilot.apk \
  --output-dir goldens/phase9 \
  --name my_new_state

# With TCP connection (e.g., Docker sidecar):
python goldens/capture_emulator.py \
  --host localhost \
  --port 5555 \
  --apk bazel-bin/android/vanpilot.apk \
  --output-dir goldens/phase9 \
  --name my_new_state
```

The script waits 10 seconds after app launch for the UI to settle before capturing.

### Method 2: Using `capture_dhu.sh` (macOS DHU window capture)

This captures the DHU window directly on macOS using `screencapture`:

```bash
# Capture current DHU window:
scripts/capture_dhu.sh goldens/phase9/dhu_screenshot.png
```

This uses macOS CoreGraphics to find the DHU window by name and capture it. Useful for capturing exactly what the DHU renders (as opposed to the full emulator screen).

### Method 3: Using `dhu.sh screenshot`

Sends a screenshot command to the DHU via its command pipe:

```bash
scripts/dhu.sh screenshot goldens/phase9/dhu_shot.png
```

### Method 4: Using `generate_goldens.py` (synthetic goldens)

For goldens that don't require a running emulator (e.g., solid color surfaces):

```bash
bazel run //goldens:generate_goldens
# Writes to goldens/phase3/solid_color_surface.png
```

### Committing new goldens

After capturing and visually verifying:

```bash
# Verify the image looks correct (open in Preview, etc.)
open goldens/phase9/my_new_state.png

# Add and commit:
git add goldens/phase9/my_new_state.png
git commit -m "Add golden for my_new_state"
```

## Updating Goldens When UI Changes

When a UI change causes golden tests to fail:

1. **Run the failing test** to generate the diff:
   ```bash
   bazel test //goldens:emulator_golden_test
   ```

2. **Review the diff image** to confirm the change is intentional:
   ```bash
   open bazel-testlogs/goldens/emulator_golden_test/test.outputs/diff.png
   open bazel-testlogs/goldens/emulator_golden_test/test.outputs/actual.png
   ```

3. **Re-capture the golden** using the appropriate method above. For example:
   ```bash
   python goldens/capture_emulator.py \
     --native \
     --output-dir goldens/phase9 \
     --name emulator_screenshot
   ```

4. **Commit the updated golden.** The PR diff shows the before/after image change, which is the primary review mechanism:
   ```bash
   git add goldens/phase9/emulator_screenshot.png
   git commit -m "Update golden for <description of UI change>"
   ```

For synthetic goldens (phase3):

```bash
bazel run //goldens:generate_goldens
git add goldens/phase3/
git commit -m "Regenerate phase3 goldens"
```

## Video Capture (Diagnostics)

For debugging golden test failures, enable video capture to record the last N seconds of emulator screen leading up to the golden frame:

```bash
# Enable with default 5-second duration:
bazel test //goldens:emulator_golden_test \
  --test_arg=--record-video

# Custom duration:
bazel test //goldens:emulator_golden_test \
  --test_arg=--record-video-duration=10
```

Videos are saved to `TEST_UNDECLARED_OUTPUTS_DIR` (typically `bazel-testlogs/.../test.outputs/`) as `.mp4` files. Videos are **not** committed to the repo.

When disabled (the default), video capture has zero overhead.

## CI vs Local

### Local (macOS host)

- Start the emulator and DHU manually (or use `scripts/dhu.sh start`)
- Run emulator-based golden tests explicitly: `bazel test //goldens:emulator_golden_test`
- Unit-level golden tests (e.g., `solid_color_surface_test`, `golden_diff_test`) run without any emulator

### CI

- Unit-level golden tests run in `bazel test //...` — no special setup needed
- Emulator-based tests are tagged `manual` and excluded from `bazel test //...` by default
- To run emulator tests in CI, the pipeline must:
  1. Start an emulator (e.g., via the emulator instance manager service — see `docs/emulator-instance-manager.md`)
  2. Explicitly target the test: `bazel test //goldens:emulator_golden_test --test_env=EMU_HOST=... --test_env=EMU_PORT=...`
- Golden diff images (`diff.png`, `actual.png`) should be uploaded as CI artifacts for PR review (see AC-12.3)

### Docker sidecar mode

When running inside Docker (e.g., Claude agent sandbox), the emulator runs as a sidecar container accessible over TCP:

```bash
python goldens/capture_emulator.py \
  --host localhost \
  --port 5555 \
  --apk bazel-bin/android/vanpilot.apk
```

The test also supports this mode via environment variables:

```bash
bazel test //goldens:emulator_golden_test \
  --test_env=EMU_HOST=localhost \
  --test_env=EMU_PORT=5555
```

## Golden Comparison Details

The `golden_diff.py` module performs pixel-by-pixel comparison:

- **Tolerance**: Configurable per-channel tolerance (default 0 = exact match). The emulator test uses tolerance=5 to account for minor rendering variations.
- **Diff image**: Changed pixels are shown in red; unchanged pixels are dimmed to 1/3 brightness.
- **Size mismatch**: If dimensions differ, the comparison fails immediately with a red placeholder diff image.
- **PNG support**: 8-bit RGB and RGBA PNGs. All standard filter types (None, Sub, Up, Average, Paeth) are supported.

## Naming Conventions

Follow the naming scheme from `goldens/README.md`:

```
goldens/
├── phase3/
│   ├── solid_color_surface.png
│   ├── solid_dark_teal_800x480.png
│   └── solid_teal_800x480.png
├── phase9/
│   └── emulator_screenshot.png
├── auto_dashboard_day.png
├── auto_dashboard_night.png
├── auto_tab_lead_agent.png
└── ...
```

Use descriptive names: `auto_<screen>_<variant>.png` for Android Auto states, `phone_<screen>.png` for phone fallback states.

## Troubleshooting

### "No emulator available" skip

The emulator golden test skips if no emulator is discovered. Check:
- `adb devices` shows your emulator as `device` (not `offline`)
- If using TCP mode, `EMU_HOST` and `EMU_PORT` environment variables are set

### DHU window not found (`capture_dhu.sh`)

The script searches for a window with "desktop-head" in the owner name. Ensure:
- The DHU is running (`scripts/dhu.sh status`)
- You're on macOS (this script uses CoreGraphics APIs)

### Screenshots too small or corrupt

- Wait for the emulator to fully boot: `adb shell getprop sys.boot_completed` should return `1`
- Ensure the app is installed and launched before capturing
- `capture_emulator.py` waits 10 seconds for render settling; for complex UIs you may need to increase `RENDER_SETTLE_TIME`

### Golden diff shows unexpected changes

- Minor rendering differences across emulator versions are expected — use tolerance > 0
- If the diff is entirely red (full mismatch), check for resolution/orientation changes
- Verify your emulator AVD matches the expected display configuration
