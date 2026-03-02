# APK Signing Setup

This document explains how to build a release-signed APK for VanPilot.

## Debug Signing (default)

The committed `android/keystores/debug.keystore` is used automatically for local development and emulator testing:

```
bazel build //android:vanpilot
```

The debug keystore uses the standard Android debug credentials (alias `androiddebugkey`, password `android`). It is safe to commit because it is only used for non-production builds.

## Release Signing

Release builds are signed via `android/keystores/sign_release.sh`, which reads credentials from environment variables. The release keystore is **never committed** — it is listed in `.gitignore`.

### Required environment variables

| Variable | Description |
|---|---|
| `VANPILOT_RELEASE_KEYSTORE` | Absolute path to the release `.keystore` file |
| `VANPILOT_RELEASE_KEYSTORE_PASS` | Keystore password |
| `VANPILOT_RELEASE_KEY_ALIAS` | Key alias within the keystore |
| `VANPILOT_RELEASE_KEY_PASS` | Key password |

### Building a release APK

1. Set the environment variables listed above in your shell (or a local `.env` file that you source — do not commit it).

2. Run:

```
bazel build //android:vanpilot_release_apk
```

Bazel passes environment variables to the genrule action automatically when they are set in the shell. The output APK is written to `bazel-bin/android/vanpilot-release.apk`.

### Generating a new release keystore

If you need to create a new release keystore (first-time setup):

```bash
keytool -genkeypair \
  -keystore release.keystore \
  -alias vanpilot-release \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

Store the keystore and its passwords in a secrets manager (e.g., 1Password). Do not commit the keystore file or passwords to the repository.

## Bazel targets

| Target | Description |
|---|---|
| `//android:vanpilot` | Debug-signed APK (uses committed debug keystore) |
| `//android:vanpilot_release_apk` | Release-signed APK (requires env vars above) |
| `//android/keystores:sign_release` | Signing script (sh_binary, callable directly) |
| `//android/keystores:debug_keystore_test` | Verifies the committed debug keystore is valid |
| `//android/keystores:sign_release_test` | Verifies sign_release.sh validates env vars correctly |
