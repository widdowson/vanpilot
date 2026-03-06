#!/usr/bin/env python3
"""Standalone CLI client for the instance manager gRPC service.

This client requires only grpcio + protobuf (both pip-installable) and
uses vendored proto stubs — no Bazel needed. Designed for use inside
Docker sandbox agents.

Usage (via wrapper script):
    im list
    im create --name my-instance
    im install-apk --name my-instance --apk vanpilot.apk
    im launch-app --name my-instance
    im destroy --name my-instance
    im screenshot --name my-instance

Set IM_ADDR to override the default server address (localhost:50061).
"""

from __future__ import annotations

import argparse
import os
import sys

# Add vendored directory to path so we can import the proto stubs
_VENDORED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendored")
if _VENDORED_DIR not in sys.path:
    sys.path.insert(0, _VENDORED_DIR)

import grpc
import instance_manager_pb2 as pb

_SERVICE = "/vanpilot.v1.InstanceManagerService"
_STATE_NAMES = {0: "UNSPECIFIED", 1: "CREATING", 2: "RUNNING", 3: "ERROR", 4: "DESTROYING"}


def _make_stubs(channel):
    """Build low-level unary-unary stubs."""
    def _stub(method, req_type, resp_type):
        return channel.unary_unary(
            f"{_SERVICE}/{method}",
            request_serializer=req_type.SerializeToString,
            response_deserializer=resp_type.FromString,
        )

    return {
        "create": _stub("CreateInstance", pb.CreateInstanceRequest, pb.CreateInstanceResponse),
        "destroy": _stub("DestroyInstance", pb.DestroyInstanceRequest, pb.DestroyInstanceResponse),
        "list": _stub("ListInstances", pb.ListInstancesRequest, pb.ListInstancesResponse),
        "get": _stub("GetInstance", pb.GetInstanceRequest, pb.GetInstanceResponse),
        "screenshot": _stub("ScreenshotInstance", pb.ScreenshotInstanceRequest, pb.ScreenshotInstanceResponse),
        "restart_dhu": _stub("RestartDhu", pb.RestartDhuRequest, pb.RestartDhuResponse),
        "dhu_command": _stub("DhuCommand", pb.DhuCommandRequest, pb.DhuCommandResponse),
        "install_apk": _stub("InstallApk", pb.InstallApkRequest, pb.InstallApkResponse),
        "adb_shell": _stub("AdbShell", pb.AdbShellRequest, pb.AdbShellResponse),
        "adb_push": _stub("AdbPush", pb.AdbPushRequest, pb.AdbPushResponse),
        "adb_pull": _stub("AdbPull", pb.AdbPullRequest, pb.AdbPullResponse),
    }


def _print_instance(info):
    state = _STATE_NAMES.get(info.state, f"UNKNOWN({info.state})")
    print(f"  {info.name}  state={state}  console={info.emulator_console_port}"
          f"  adb={info.adb_port}  aa={info.aa_forward_port}"
          f"  headful={info.headful}  avd={info.avd_name}")
    if info.last_screenshot_png:
        print(f"    DHU screenshot: {len(info.last_screenshot_png)} bytes")
    if info.last_emulator_screenshot_png:
        print(f"    Phone screenshot: {len(info.last_emulator_screenshot_png)} bytes")


def cmd_create(stubs, args):
    req = pb.CreateInstanceRequest(
        name=args.name,
        headful=args.headful,
        avd_name=args.avd or "",
        snapshot_name=args.snapshot or "",
    )
    print(f"Creating instance '{args.name}'...")
    resp = stubs["create"](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def cmd_destroy(stubs, args):
    stubs["destroy"](pb.DestroyInstanceRequest(name=args.name), timeout=30)
    print(f"Destroyed '{args.name}'")


def cmd_list(stubs, args):
    resp = stubs["list"](pb.ListInstancesRequest(), timeout=10)
    if not resp.instances:
        print("No instances.")
        return
    for info in resp.instances:
        _print_instance(info)


def cmd_get(stubs, args):
    resp = stubs["get"](pb.GetInstanceRequest(name=args.name), timeout=10)
    _print_instance(resp.instance)


def cmd_screenshot(stubs, args):
    resp = stubs["screenshot"](pb.ScreenshotInstanceRequest(name=args.name), timeout=30)
    if resp.dhu_screenshot_png:
        dhu_path = args.output or f"/tmp/{args.name}_dhu.png"
        with open(dhu_path, "wb") as f:
            f.write(resp.dhu_screenshot_png)
        print(f"DHU screenshot: {dhu_path} ({len(resp.dhu_screenshot_png)} bytes)")
    if resp.emulator_screenshot_png:
        emu_path = args.emu_output or f"/tmp/{args.name}_phone.png"
        with open(emu_path, "wb") as f:
            f.write(resp.emulator_screenshot_png)
        print(f"Phone screenshot: {emu_path} ({len(resp.emulator_screenshot_png)} bytes)")


def cmd_restart_dhu(stubs, args):
    req = pb.RestartDhuRequest(name=args.name)
    print(f"Restarting DHU for '{args.name}'...")
    resp = stubs["restart_dhu"](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def cmd_dhu_command(stubs, args):
    command = " ".join(args.dhu_words)
    req = pb.DhuCommandRequest(
        name=args.name,
        command=command,
        capture_screenshot=args.screenshot,
    )
    resp = stubs["dhu_command"](req, timeout=30)
    print(f"Command sent at {resp.executed_at_ms}")
    if resp.screenshot_png:
        out_path = args.output or f"/tmp/{args.name}_dhu_cmd.png"
        with open(out_path, "wb") as f:
            f.write(resp.screenshot_png)
        print(f"Screenshot: {out_path} ({len(resp.screenshot_png)} bytes)")


def cmd_launch_app(stubs, args):
    import time

    def dhu(command, screenshot=False):
        req = pb.DhuCommandRequest(
            name=args.name,
            command=command,
            capture_screenshot=screenshot,
        )
        return stubs["dhu_command"](req, timeout=30)

    print(f"Launching VanPilot on '{args.name}'...")

    # Step 1: Open the app launcher
    dhu("keycode home")
    print("  Opened launcher, waiting for grid...")
    time.sleep(2)

    # Step 2: Tap VanPilot's icon at (200, 390) in the 1920x1080 grid
    resp = dhu(f"tap {args.x} {args.y}", screenshot=args.screenshot)
    print(f"  Tapped ({args.x}, {args.y}), waiting for app init...")
    time.sleep(args.wait)

    if resp.screenshot_png:
        out_path = args.output or f"/tmp/{args.name}_launch.png"
        with open(out_path, "wb") as f:
            f.write(resp.screenshot_png)
        print(f"  Screenshot: {out_path} ({len(resp.screenshot_png)} bytes)")

    print("Done — VanPilot should be running.")


def cmd_install_apk(stubs, args):
    apk_path = args.apk
    with open(apk_path, "rb") as f:
        apk_data = f.read()
    print(f"Installing {apk_path} ({len(apk_data)} bytes) on '{args.name}'...")
    req = pb.InstallApkRequest(
        name=args.name,
        apk_data=apk_data,
        restart_dhu=args.restart_dhu,
    )
    resp = stubs["install_apk"](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def cmd_adb(stubs, args):
    shell_args = args.shell_args
    # REMAINDER includes "--" when used as separator; strip it
    if shell_args and shell_args[0] == "--":
        shell_args = shell_args[1:]
    req = pb.AdbShellRequest(
        name=args.name,
        args=shell_args,
        timeout_s=args.timeout,
    )
    resp = stubs["adb_shell"](req, timeout=args.timeout + 5)
    if resp.stdout:
        sys.stdout.write(resp.stdout)
    if resp.stderr:
        sys.stderr.write(resp.stderr)
    sys.exit(resp.exit_code)


def cmd_push(stubs, args):
    with open(args.file, "rb") as f:
        data = f.read()
    print(f"Pushing {args.file} ({len(data)} bytes) to {args.remote} on '{args.name}'...")
    req = pb.AdbPushRequest(
        name=args.name,
        data=data,
        remote_path=args.remote,
    )
    stubs["adb_push"](req, timeout=args.timeout)
    print("OK")


def cmd_pull(stubs, args):
    print(f"Pulling {args.remote} from '{args.name}'...")
    req = pb.AdbPullRequest(
        name=args.name,
        remote_path=args.remote,
    )
    resp = stubs["adb_pull"](req, timeout=args.timeout)
    out_path = args.output or os.path.basename(args.remote)
    with open(out_path, "wb") as f:
        f.write(resp.data)
    print(f"OK — {len(resp.data)} bytes written to {out_path}")


def build_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Instance manager CLI (standalone, no Bazel needed)",
    )
    default_addr = os.environ.get("IM_ADDR", "localhost:50061")
    parser.add_argument("--addr", default=default_addr, help="gRPC server address")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--avd", default="")
    p_create.add_argument("--snapshot", default="")
    p_create.add_argument("--headful", action="store_true")
    p_create.add_argument("--timeout", type=int, default=180)

    p_destroy = sub.add_parser("destroy")
    p_destroy.add_argument("--name", required=True)

    sub.add_parser("list")

    p_get = sub.add_parser("get")
    p_get.add_argument("--name", required=True)

    p_ss = sub.add_parser("screenshot")
    p_ss.add_argument("--name", required=True)
    p_ss.add_argument("--output", help="DHU screenshot output path")
    p_ss.add_argument("--emu-output", help="Phone screenshot output path")

    p_restart = sub.add_parser("restart-dhu")
    p_restart.add_argument("--name", required=True)
    p_restart.add_argument("--timeout", type=int, default=120)

    p_dhu_cmd = sub.add_parser("dhu-command")
    p_dhu_cmd.add_argument("--name", required=True)
    p_dhu_cmd.add_argument("--screenshot", action="store_true")
    p_dhu_cmd.add_argument("--output", help="Screenshot output path")
    p_dhu_cmd.add_argument("dhu_words", nargs="+", metavar="command", help="DHU console command")

    p_launch = sub.add_parser("launch-app",
                               help="Launch VanPilot on the DHU via launcher tap")
    p_launch.add_argument("--name", required=True)
    p_launch.add_argument("--x", type=int, default=200, help="Tap X coord (default: 200)")
    p_launch.add_argument("--y", type=int, default=390, help="Tap Y coord (default: 390)")
    p_launch.add_argument("--wait", type=int, default=5, help="Seconds to wait after tap")
    p_launch.add_argument("--screenshot", action="store_true", help="Capture screenshot after tap")
    p_launch.add_argument("--output", help="Screenshot output path")

    p_install = sub.add_parser("install-apk")
    p_install.add_argument("--name", required=True)
    p_install.add_argument("--apk", required=True, help="Path to APK file")
    p_install.add_argument("--restart-dhu", action="store_true", default=True,
                           help="Restart DHU after install (default: true)")
    p_install.add_argument("--no-restart-dhu", dest="restart_dhu", action="store_false",
                           help="Skip DHU restart after install")
    p_install.add_argument("--timeout", type=int, default=180)

    p_adb = sub.add_parser("adb")
    p_adb.add_argument("--name", required=True)
    p_adb.add_argument("--timeout", type=int, default=30)
    p_adb.add_argument("shell_args", nargs=argparse.REMAINDER, metavar="arg",
                        help="adb shell command + args (use -- before args starting with -)")

    p_push = sub.add_parser("adb-push")
    p_push.add_argument("--name", required=True)
    p_push.add_argument("--file", required=True,
                         help="Local file to push (max ~4MB due to gRPC message size limit)")
    p_push.add_argument("--remote", required=True, help="Remote path on emulator")
    p_push.add_argument("--timeout", type=int, default=60)

    p_pull = sub.add_parser("adb-pull")
    p_pull.add_argument("--name", required=True)
    p_pull.add_argument("--remote", required=True, help="Remote path on emulator")
    p_pull.add_argument("--output", help="Local output path (default: basename of remote)")
    p_pull.add_argument("--timeout", type=int, default=60)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    channel = grpc.insecure_channel(args.addr)
    stubs = _make_stubs(channel)

    dispatch = {
        "create": cmd_create,
        "destroy": cmd_destroy,
        "list": cmd_list,
        "get": cmd_get,
        "screenshot": cmd_screenshot,
        "restart-dhu": cmd_restart_dhu,
        "dhu-command": cmd_dhu_command,
        "install-apk": cmd_install_apk,
        "adb": cmd_adb,
        "adb-push": cmd_push,
        "adb-pull": cmd_pull,
        "launch-app": cmd_launch_app,
    }
    try:
        dispatch[args.command](stubs, args)
    except grpc.RpcError as e:
        print(f"ERROR: {e.code()} — {e.details()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
