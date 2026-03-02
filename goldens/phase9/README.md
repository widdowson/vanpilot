# Phase 9: Emulator-Based Golden Screenshots

This directory contains golden screenshots captured from a real Android emulator
running the VanPilot app with the Android Auto DHU (Desktop Head Unit).

## How screenshots are captured

1. The emulator sidecar container runs an x86_64 Android emulator with software rendering
2. The VanPilot APK is installed on the emulator
3. Screenshots are captured via `adb screencap`
4. For DHU screenshots, the DHU `screenshot` command captures the Android Auto display

## Capture command

```bash
# Start the emulator sidecar
docker run --platform linux/amd64 -d --name vanpilot-emu -p 5555:5555 vanpilot-emu

# Wait for boot, then capture
python goldens/capture_emulator.py --apk bazel-bin/android/vanpilot.apk
```

## Test command

```bash
bazel test //goldens:emulator_golden_test \
  --test_env=EMU_HOST=localhost --test_env=EMU_PORT=5555
```

## Notes

- Software rendering on ARM64 hosts takes 5-15 minutes to boot
- Screenshots may vary slightly between emulator versions (use tolerance in comparison)
- The `emulator_golden_test` is tagged `manual` — it does not run during `bazel test //...`
