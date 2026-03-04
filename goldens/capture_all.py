"""Capture all golden screenshots for VanPilot Android Auto UI states.

Uses the instance manager gRPC client to create an emulator+DHU instance,
install the APK, drive each UI state, and capture screenshots.

Usage:
    bazel run //goldens:capture_all -- \\
        --instance-manager-addr localhost:50061 \\
        --apk bazel-bin/android/vanpilot.apk \\
        --output-dir goldens/

Env vars:
    INSTANCE_MANAGER_ADDR: gRPC address (default "localhost:50061")
    VANPILOT_APK: Path to the VanPilot APK
"""

import argparse
import os
import subprocess
import sys
import time

from goldens.golden_test_harness import (
    InstanceManagerClient,
    capture_emulator_screenshot,
    install_apk,
    launch_vanpilot_app,
)

RENDER_SETTLE_TIME = 10  # seconds to wait for rendering to stabilize
TAB_SWITCH_SETTLE = 3  # seconds to wait after tab switch


def _adb_shell(adb_port: int, *args: str, timeout: int = 15) -> str:
    """Run an ADB shell command against the emulator."""
    serial = f"localhost:{adb_port}"
    result = subprocess.run(
        ["adb", "-s", serial, "shell", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def _send_dhu_command(adb_port: int, command: str) -> None:
    """Send a command to the DHU via the DHU command channel.

    The DHU listens on a TCP socket for commands. Common commands:
      day/night - toggle light/dark mode
      select N  - select tab N (0-indexed)
    """
    # TODO: Implement DHU command channel. The DHU exposes a TCP command
    # socket that can be used to toggle day/night mode and interact with
    # the AA UI. For now, use adb shell input commands as a workaround.
    print(f"  [DHU CMD] {command}")


def _tap_tab(adb_port: int, tab_index: int) -> None:
    """Tap a tab in the Android Auto tab bar.

    Tab bar is at the bottom of the DHU screen. Tab positions are
    approximately evenly spaced across the screen width.

    Args:
        adb_port: ADB port of the emulator.
        tab_index: 0-indexed tab position.
    """
    # TODO: Calculate actual tap coordinates based on DHU screen dimensions.
    # For now, log the intent -- actual coordinates depend on DHU resolution.
    print(f"  [TAP] Tab {tab_index}")


def capture_state(
    client: InstanceManagerClient,
    instance_name: str,
    adb_port: int,
    state_name: str,
    output_dir: str,
    settle_time: float = TAB_SWITCH_SETTLE,
) -> str:
    """Capture a single UI state screenshot.

    Args:
        client: Instance manager client.
        instance_name: Name of the emulator instance.
        adb_port: ADB port of the emulator.
        state_name: Descriptive filename (without extension).
        output_dir: Directory to save the screenshot.
        settle_time: Seconds to wait before capture.

    Returns:
        Path to the saved PNG file.
    """
    time.sleep(settle_time)
    output_path = os.path.join(output_dir, f"{state_name}.png")

    # Try DHU screenshot first, fall back to emulator screencap
    try:
        resp = client.screenshot_instance(instance_name)
        if resp.dhu_screenshot_png:
            with open(output_path, "wb") as f:
                f.write(resp.dhu_screenshot_png)
            size = len(resp.dhu_screenshot_png)
            print(f"  Captured (DHU): {output_path} ({size} bytes)")
            return output_path
    except Exception as e:
        print(f"  DHU screenshot failed ({e}), falling back to screencap")

    png_data = capture_emulator_screenshot(adb_port)
    with open(output_path, "wb") as f:
        f.write(png_data)
    print(f"  Captured (emu): {output_path} ({len(png_data)} bytes)")
    return output_path


def capture_all_states(
    instance_manager_addr: str,
    apk_path: str,
    output_dir: str,
) -> list[str]:
    """Capture all golden screenshots.

    Returns list of captured file paths.
    """
    captured = []
    client = InstanceManagerClient(instance_manager_addr)
    instance_name = "golden-capture-all"

    try:
        # Create instance
        print(f"Creating instance '{instance_name}'...")
        resp = client.create_instance(name=instance_name)
        instance = resp.instance
        adb_port = instance.adb_port
        print(f"  Instance created: adb_port={adb_port}")

        # Install APK
        if apk_path:
            print(f"Installing APK: {apk_path}")
            install_apk(adb_port, apk_path)
            launch_vanpilot_app(adb_port)
            print(f"Waiting {RENDER_SETTLE_TIME}s for initial render...")
            time.sleep(RENDER_SETTLE_TIME)
        else:
            print("WARNING: No APK path provided -- skipping install")

        os.makedirs(output_dir, exist_ok=True)

        # ================================================================
        # 1. Visual Card Tab -- Light Mode (default state)
        # ================================================================
        print("\n[1/8] Visual Card -- Light Mode (default)")
        _send_dhu_command(adb_port, "day")
        path = capture_state(
            client, instance_name, adb_port,
            "visual_card_light", output_dir,
            settle_time=RENDER_SETTLE_TIME,
        )
        captured.append(path)

        # ================================================================
        # 2. Visual Card Tab -- Dark Mode
        # ================================================================
        print("\n[2/8] Visual Card -- Dark Mode")
        _send_dhu_command(adb_port, "night")
        path = capture_state(
            client, instance_name, adb_port,
            "visual_card_dark", output_dir,
        )
        captured.append(path)

        # Switch back to light mode for remaining captures
        _send_dhu_command(adb_port, "day")
        time.sleep(TAB_SWITCH_SETTLE)

        # ================================================================
        # 3. Lead Agent Tab -- with mock messages
        # ================================================================
        print("\n[3/8] Lead Agent Tab -- populated")
        _tap_tab(adb_port, 1)  # Tab index 1 = Lead Agent
        path = capture_state(
            client, instance_name, adb_port,
            "lead_agent_populated", output_dir,
        )
        captured.append(path)

        # ================================================================
        # 4. Sub-Agent Tab -- Researcher
        # ================================================================
        print("\n[4/8] Sub-Agent Tab -- Researcher")
        _tap_tab(adb_port, 2)  # Tab index 2 = first sub-agent
        path = capture_state(
            client, instance_name, adb_port,
            "sub_agent_researcher", output_dir,
        )
        captured.append(path)

        # ================================================================
        # 5. Sub-Agent Tab -- Coder
        # ================================================================
        print("\n[5/8] Sub-Agent Tab -- Coder")
        _tap_tab(adb_port, 3)  # Tab index 3 = second sub-agent
        path = capture_state(
            client, instance_name, adb_port,
            "sub_agent_coder", output_dir,
        )
        captured.append(path)

        # ================================================================
        # 6. All 4 tabs visible -- overview
        # ================================================================
        print("\n[6/8] All 4 Tabs -- Visual selected")
        _tap_tab(adb_port, 0)  # Back to Visual tab
        path = capture_state(
            client, instance_name, adb_port,
            "all_tabs_visual_selected", output_dir,
        )
        captured.append(path)

        # ================================================================
        # 7. Custom bitmap displayed
        # ================================================================
        print("\n[7/8] Custom Bitmap Displayed")
        # TODO: Send a BitmapPayload event via gRPC to display a test bitmap
        # on the Visual Card surface. This requires the SyncService polling
        # loop to be active and the bitmap to be cached+displayed.
        print("  SKIPPED -- requires gRPC bitmap injection")

        # ================================================================
        # 8. Dark mode with Lead Agent tab
        # ================================================================
        print("\n[8/8] Lead Agent -- Dark Mode")
        _send_dhu_command(adb_port, "night")
        _tap_tab(adb_port, 1)
        path = capture_state(
            client, instance_name, adb_port,
            "lead_agent_dark", output_dir,
        )
        captured.append(path)

    finally:
        print(f"\nDestroying instance '{instance_name}'...")
        try:
            client.destroy_instance(instance_name)
        except Exception as e:
            print(f"  Warning: destroy failed: {e}")
        client.close()

    return captured


def main():
    parser = argparse.ArgumentParser(
        description="Capture all VanPilot golden screenshots"
    )
    parser.add_argument(
        "--instance-manager-addr",
        default=os.environ.get("INSTANCE_MANAGER_ADDR", "localhost:50061"),
        help="Instance manager gRPC address (default: localhost:50061)",
    )
    parser.add_argument(
        "--apk",
        default=os.environ.get("VANPILOT_APK", ""),
        help="Path to VanPilot APK (skips install if unset)",
    )
    parser.add_argument(
        "--output-dir",
        default="goldens/captured",
        help="Output directory for screenshots (default: goldens/captured)",
    )
    args = parser.parse_args()

    captured = capture_all_states(
        instance_manager_addr=args.instance_manager_addr,
        apk_path=args.apk,
        output_dir=args.output_dir,
    )

    print(f"\n{'='*60}")
    print(f"Captured {len(captured)} golden screenshots:")
    for path in captured:
        print(f"  {path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
