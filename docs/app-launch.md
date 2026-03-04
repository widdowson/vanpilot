# Launching VanPilot on the Android Auto DHU

This document describes how to reliably launch VanPilot on the Android Auto
Desktop Head Unit (DHU) after a fresh APK install.

## Quick Reference

```bash
# Full flow: create instance → install → launch
python3 standalone_client.py create --name my-instance
python3 standalone_client.py install-apk --name my-instance --apk vanpilot.apk
python3 standalone_client.py launch-app --name my-instance [--screenshot]
```

## Launch Mechanism

VanPilot is a **Car App Library** app (not an old-style navigation projection
client). Android Auto discovers it via the `CarAppService` intent filter and
shows it in the app launcher grid. The launch sequence:

1. **Open the app launcher** — DHU command `keycode home`
2. **Wait for the launcher grid** — ~1-2 seconds for rendering
3. **Tap VanPilot's icon** — DHU command `tap 200 390`
4. **Wait for initialization** — ~5-10 seconds for session creation

The DHU uses a **1920×1080 coordinate system** for `tap` commands (matching
the screenshot resolution). VanPilot appears in the launcher grid at
approximately row 3, column 1 — coordinates **(200, 390)**.

## What Doesn't Work

| Approach | Why it fails |
|---|---|
| `default_navigation_app` setting | Only works for old-style NavigationClient projection, not Car App Library |
| `am start -n .../VanPilotCarAppService` | Can't start a Car App Library service from the shell |
| `am start-foreground-service` | Starts the process but Android Auto doesn't bind |
| DHU `dpad` navigation + `dpad_center` | Dpad events don't reach the launcher grid in headless mode |

## Manifest Requirements

The app's `automotive_app_desc.xml` must declare **only** `template`:

```xml
<automotiveApp>
    <uses name="template" />
</automotiveApp>
```

**Do NOT include `<uses name="navigation" />`** — this triggers Gearhead's
`NavClientManager` to try the old-style navigation projection binding, which
fails with "No Navigation Client Source".

The `NAVIGATION` category in the `CarAppService` intent filter is still
required (and correct) for `NavigationTemplate` + `SurfaceCallback` access:

```xml
<service android:name=".VanPilotCarAppService" android:exported="true">
    <intent-filter>
        <action android:name="androidx.car.app.CarAppService" />
        <category android:name="androidx.car.app.category.NAVIGATION" />
    </intent-filter>
</service>
```

## Coordinate Discovery

To find VanPilot's position if the launcher grid layout changes:

1. Take a DHU screenshot (`screenshot` command)
2. Open the launcher (`keycode home`)
3. Tap known icons (e.g., Maps at ~(1090, 90)) and verify via logcat
4. Search for `makeForeground` in logcat — a successful tap logs:
   `CAR.CAM : makeForeground for component ComponentInfo{com.vanpilot.auto/...}`

Grid layout (at 1920×1080, with `aa_ready` snapshot + VanPilot installed):

| | Col 1 (~200) | Col 2 (~400) | Col 3 (~600) | Col 4 (~800) | Col 5 (~1090) |
|---|---|---|---|---|---|
| Row 1 (~90) | Exit | All vehicle apps | Calendar | GameSnacks | Maps |
| Row 2 (~240) | Messages | News | Phone | Reminder | Settings |
| Row 3 (~390) | **VanPilot** | Weather | YT Music | Customize | |

## Troubleshooting

### "VanPilot isn't responding"

Check logcat for the specific error:

- **`No Navigation Client Source`** — Remove `<uses name="navigation"/>` from
  `automotive_app_desc.xml`
- **`ANR API: BIND`** — The host can't bind to the app. Check
  `minCarApiLevel` isn't higher than the host supports. Also check for
  crashes in `onCreateScreen()`.
- **`ProviderNotFoundException: No functional channel service provider`** —
  The gRPC runtime (grpc-okhttp) isn't packaged in the APK. Ensure the
  build includes it, or handle the error gracefully in `onCreateScreen()`.

### VanPilot not in launcher

- Verify APK is installed: `adb shell pm list packages | grep vanpilot`
- Check DHU was restarted after install (Gearhead scans for new apps on connect)
- Look for "new app notification" in logcat:
  `GH.AppNotifier: Posting notification for new app ComponentInfo{com.vanpilot.auto/...}`
