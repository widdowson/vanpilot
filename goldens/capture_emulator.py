"""Automated golden screenshot capture via Android emulator + DHU sidecar.

This module connects to a running emulator sidecar container, installs the
VanPilot APK, launches the Android Auto DHU, and captures screenshots.

The emulator sidecar must already be running:
  docker run --platform linux/amd64 -d --name vanpilot-emu -p 5555:5555 vanpilot-emu

Usage:
  python goldens/capture_emulator.py [--host localhost] [--port 5555] [--output goldens/phase9/]
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555
DEFAULT_OUTPUT_DIR = "goldens/phase9"
BOOT_TIMEOUT = 300  # 5 minutes for software rendering
RENDER_SETTLE_TIME = 10  # seconds to wait after app launch
DHU_SETTLE_TIME = 5  # seconds to wait after DHU start


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


def wait_for_adb(host: str, port: int, timeout: int = BOOT_TIMEOUT) -> None:
    """Connect to ADB and wait for the emulator to finish booting."""
    addr = f"{host}:{port}"
    print(f"Connecting to ADB at {addr}...")
    run_cmd(["adb", "connect", addr], timeout=30)

    print(f"Waiting for boot (up to {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = run_cmd(
                ["adb", "-s", addr, "shell", "getprop", "sys.boot_completed"],
                timeout=10,
            )
            if result.stdout.strip() == "1":
                print("Emulator booted.")
                return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        time.sleep(5)

    raise TimeoutError(f"Emulator did not boot within {timeout}s")


def install_apk(host: str, port: int, apk_path: str) -> None:
    """Install the VanPilot APK on the emulator."""
    addr = f"{host}:{port}"
    print(f"Installing {apk_path}...")
    run_cmd(["adb", "-s", addr, "install", "-r", apk_path], timeout=120)
    print("APK installed.")


def capture_screencap(host: str, port: int, output_path: str) -> str:
    """Capture a screenshot via adb screencap and pull it locally.

    Returns the local path to the saved PNG.
    """
    addr = f"{host}:{port}"
    remote_path = "/sdcard/golden_screenshot.png"

    print("Capturing screenshot via adb screencap...")
    run_cmd(["adb", "-s", addr, "shell", "screencap", "-p", remote_path])
    run_cmd(["adb", "-s", addr, "pull", remote_path, output_path])
    run_cmd(["adb", "-s", addr, "shell", "rm", remote_path])

    size = os.path.getsize(output_path)
    print(f"Screenshot saved to {output_path} ({size} bytes)")
    return output_path


def launch_app(host: str, port: int) -> None:
    """Launch the VanPilot car app service."""
    addr = f"{host}:{port}"
    print("Launching VanPilot car app service...")
    # The CarAppService is started by the DHU, but we can also start
    # the main activity to ensure the service is initialized
    try:
        run_cmd(
            [
                "adb",
                "-s",
                addr,
                "shell",
                "am",
                "start",
                "-n",
                "com.vanpilot.auto/.VanPilotCarAppService",
            ],
            timeout=15,
        )
    except subprocess.CalledProcessError:
        # CarAppService may not be directly startable — that's OK,
        # the DHU will trigger it
        print("  (Service will be started by DHU)")


def capture_golden(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    apk_path: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    name: str = "emulator_screenshot",
) -> str:
    """Full capture workflow: connect, install, launch, screenshot.

    Args:
        host: Emulator sidecar host.
        port: ADB port.
        apk_path: Path to VanPilot APK (optional — skips install if None).
        output_dir: Directory to save the screenshot.
        name: Base filename (without extension).

    Returns:
        Path to the saved PNG file.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{name}.png")

    wait_for_adb(host, port)

    if apk_path:
        install_apk(host, port, apk_path)
        launch_app(host, port)
        print(f"Waiting {RENDER_SETTLE_TIME}s for app to render...")
        time.sleep(RENDER_SETTLE_TIME)

    capture_screencap(host, port, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Capture golden screenshot from Android emulator sidecar"
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--apk", help="Path to VanPilot APK")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--name", default="emulator_screenshot")
    args = parser.parse_args()

    try:
        path = capture_golden(
            host=args.host,
            port=args.port,
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
