# 13-Inch Display Goldens (AC-10.2)

Golden screenshots captured against a 13-inch automotive ultrawide display
profile (1920x720 @ 160 DPI).

## Display Profile

| Parameter | Value |
|---|---|
| DHU Resolution | 1920x720 |
| DPI | 160 |
| Screen Size | 13 inches (diagonal) |
| Aspect Ratio | 8:3 (ultrawide automotive) |

This matches common 13-inch aftermarket and OEM head unit displays
(e.g., Hyundai/Kia ultrawide infotainment).

## Capturing Goldens

1. Start the emulator and DHU with 13-inch resolution:

```bash
emulator -avd vanpilot_test &
adb wait-for-device
adb forward tcp:5277 tcp:5277
$ANDROID_HOME/extras/google/auto/desktop-head-unit --resolution 1920x720
```

2. Build and install the APK:

```bash
bazel build //android:vanpilot
adb install -r bazel-bin/android/vanpilot.apk
```

3. Run the golden test to capture:

```bash
bazel test //goldens:emulator_golden_13inch_test \
  --test_env=EMU_HOST=localhost \
  --test_env=EMU_PORT=5555
```

4. Commit the captured goldens from `TEST_UNDECLARED_OUTPUTS_DIR`.
