# Phase 3 Golden Screenshots

## Status: Pending (No Emulator/DHU Available)

This sandbox environment (Linux aarch64) does not have an Android emulator or
Desktop Head Unit (DHU) available. Golden screenshots will be captured when
the APK is deployed to an actual Android Auto emulator setup.

## What to Capture

1. **solid_color_surface.png** - The NavigationTemplate's surface filled with
   VanPilot teal (#1A8A7D), proving that SurfaceCallback.onSurfaceAvailable()
   works and canvas rendering succeeds.

2. **tab_template_layout.png** - The TabTemplate with the "Visual" tab active,
   showing the overall layout structure.

## How to Capture

```bash
# Start the Android emulator
emulator -avd Pixel_10_Pro_API_35 &

# Install the APK
adb install bazel-bin/android/vanpilot.apk

# Start the Desktop Head Unit
$ANDROID_HOME/extras/google/auto/desktop-head-unit &

# Launch the app via Android Auto
adb shell am start -n com.vanpilot.auto/.VanPilotCarAppService

# Capture screenshot from DHU
adb shell screencap -p /sdcard/screenshot.png
adb pull /sdcard/screenshot.png goldens/phase3/solid_color_surface.png
```

## Verification

The golden screenshot should show:
- A solid teal (#1A8A7D) rectangle filling the NavigationTemplate's surface area
- The TabTemplate tab bar with "Visual" tab selected
- Standard Android Auto chrome (status bar, nav bar)

## APK Build Verification

The APK builds successfully:
```
bazel build //android:vanpilot
# Produces: bazel-bin/android/vanpilot.apk
```
