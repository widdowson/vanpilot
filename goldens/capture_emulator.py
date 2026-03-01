"""Automated golden screenshot capture via Android emulator.

Supports two modes:
  1. Docker sidecar (TCP): adb connect host:port
  2. Native emulator: auto-discovered via `adb devices` as emulator-NNNN

Usage:
  # TCP sidecar
  python goldens/capture_emulator.py --host localhost --port 5555 --apk bazel-bin/android/vanpilot.apk

  # Native emulator (auto-detect)
  python goldens/capture_emulator.py --native --apk bazel-bin/android/vanpilot.apk
"""

import argparse
import os
import subprocess
import sys
import time

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555
DEFAULT_OUTPUT_DIR = "goldens/phase9"
BOOT_TIMEOUT = 300  # 5 minutes for software rendering
RENDER_SETTLE_TIME = 10  # seconds to wait after app launch


def run_cmd(
    cmd: list[str], timeout: int = 60, capture: bool = True
) -> subprocess.CompletedProcess:
    """Run a command, raising on failure."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=True,
    )


def find_native_emulator(timeout: int = 10) -> str | None:
    """Find a native emulator serial from `adb devices`.

    Returns the first emulator-NNNN serial found, or None.
    """
    try:
        result = run_cmd(["adb", "devices"], timeout=timeout)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith("emulator-") and parts[1] == "device":
                return parts[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def resolve_device(host: str | None, port: int | None, native: bool) -> str:
    """Resolve the ADB device serial to use.

    Args:
        host: TCP host (for sidecar mode).
        port: TCP port (for sidecar mode).
        native: If True, auto-detect a native emulator.

    Returns:
        ADB serial string (e.g. "localhost:5555" or "emulator-5554").
    """
    if native:
        serial = find_native_emulator()
        if serial:
            return serial
        # Fall through to TCP mode if no native emulator found
        print("No native emulator found, falling back to TCP mode...")

    addr = f"{host or DEFAULT_HOST}:{port or DEFAULT_PORT}"
    run_cmd(["adb", "connect", addr], timeout=30)
    return addr


def wait_for_boot(serial: str, timeout: int = BOOT_TIMEOUT) -> None:
    """Wait for the emulator to finish booting."""
    print(f"Waiting for boot on {serial} (up to {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = run_cmd(
                ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                timeout=10,
            )
            if result.stdout.strip() == "1":
                print("Emulator booted.")
                return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        time.sleep(5)

    raise TimeoutError(f"Emulator did not boot within {timeout}s")


def install_apk(serial: str, apk_path: str) -> None:
    """Install the VanPilot APK on the emulator."""
    print(f"Installing {apk_path}...")
    run_cmd(["adb", "-s", serial, "install", "-r", apk_path], timeout=120)
    print("APK installed.")


def capture_screencap(serial: str, output_path: str) -> str:
    """Capture a screenshot via adb screencap and pull it locally.

    Returns the local path to the saved PNG.
    """
    remote_path = "/sdcard/golden_screenshot.png"

    print("Capturing screenshot via adb screencap...")
    run_cmd(["adb", "-s", serial, "shell", "screencap", "-p", remote_path])
    run_cmd(["adb", "-s", serial, "pull", remote_path, output_path])
    run_cmd(["adb", "-s", serial, "shell", "rm", remote_path])

    size = os.path.getsize(output_path)
    print(f"Screenshot saved to {output_path} ({size} bytes)")
    return output_path


def launch_app(serial: str) -> None:
    """Launch the VanPilot car app service."""
    print("Launching VanPilot car app service...")
    try:
        run_cmd(
            [
                "adb", "-s", serial, "shell", "am", "start", "-n",
                "com.vanpilot.auto/.VanPilotCarAppService",
            ],
            timeout=15,
        )
    except subprocess.CalledProcessError:
        print("  (Service will be started by DHU)")


def capture_golden(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    native: bool = False,
    apk_path: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    name: str = "emulator_screenshot",
) -> str:
    """Full capture workflow: connect, install, launch, screenshot.

    Args:
        host: Emulator sidecar host (TCP mode).
        port: ADB port (TCP mode).
        native: If True, auto-detect native emulator via adb devices.
        apk_path: Path to VanPilot APK (optional — skips install if None).
        output_dir: Directory to save the screenshot.
        name: Base filename (without extension).

    Returns:
        Path to the saved PNG file.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{name}.png")

    serial = resolve_device(host, port, native)
    wait_for_boot(serial)

    if apk_path:
        install_apk(serial, apk_path)
        launch_app(serial)
        print(f"Waiting {RENDER_SETTLE_TIME}s for app to render...")
        time.sleep(RENDER_SETTLE_TIME)

    capture_screencap(serial, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Capture golden screenshot from Android emulator"
    )
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Emulator host for TCP mode (default: localhost)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="ADB port for TCP mode (default: 5555)")
    parser.add_argument("--native", action="store_true",
                        help="Auto-detect native emulator via 'adb devices'")
    parser.add_argument("--apk", help="Path to VanPilot APK")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--name", default="emulator_screenshot")
    args = parser.parse_args()

    try:
        path = capture_golden(
            host=args.host,
            port=args.port,
            native=args.native,
            apk_path=args.apk,
            output_dir=args.output_dir,
            name=args.name,
        )
        print(f"\nGolden captured: {path}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
