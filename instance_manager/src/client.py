"""CLI client for the instance manager gRPC service."""

from __future__ import annotations

import argparse
import os
import sys

import grpc

from proto.vanpilot.v1 import instance_manager_pb2

_SERVICE = "/vanpilot.v1.InstanceManagerService"
_STATE_NAMES = {0: "UNSPECIFIED", 1: "CREATING", 2: "RUNNING", 3: "ERROR", 4: "DESTROYING"}


def _make_stubs(channel):
    """Build low-level unary-unary stubs (no gRPC codegen needed)."""
    def _stub(method, req_type, resp_type):
        return channel.unary_unary(
            f"{_SERVICE}/{method}",
            request_serializer=req_type.SerializeToString,
            response_deserializer=resp_type.FromString,
        )

    pb = instance_manager_pb2
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
        "save_snapshot": _stub("SaveSnapshot", pb.SaveSnapshotRequest, pb.SaveSnapshotResponse),
        "load_snapshot": _stub("LoadSnapshot", pb.LoadSnapshotRequest, pb.LoadSnapshotResponse),
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
    pb = instance_manager_pb2
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
    pb = instance_manager_pb2
    stubs["destroy"](pb.DestroyInstanceRequest(name=args.name), timeout=30)
    print(f"Destroyed '{args.name}'")


def cmd_list(stubs, args):
    pb = instance_manager_pb2
    resp = stubs["list"](pb.ListInstancesRequest(), timeout=10)
    if not resp.instances:
        print("No instances.")
        return
    for info in resp.instances:
        _print_instance(info)


def cmd_get(stubs, args):
    pb = instance_manager_pb2
    resp = stubs["get"](pb.GetInstanceRequest(name=args.name), timeout=10)
    _print_instance(resp.instance)


def cmd_screenshot(stubs, args):
    pb = instance_manager_pb2
    resp = stubs["screenshot"](pb.ScreenshotInstanceRequest(name=args.name), timeout=30)
    ts = resp.captured_at_ms
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
    pb = instance_manager_pb2
    req = pb.RestartDhuRequest(name=args.name)
    print(f"Restarting DHU for '{args.name}'...")
    resp = stubs["restart_dhu"](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def cmd_dhu_command(stubs, args):
    pb = instance_manager_pb2
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


def cmd_install_apk(stubs, args):
    pb = instance_manager_pb2
    apk_path = args.apk
    with open(apk_path, "rb") as f:
        apk_data = f.read()
    print(f"Installing {apk_path} ({len(apk_data)} bytes) on '{args.name}'...")
    req = pb.InstallApkRequest(
        name=args.name,
        apk_data=apk_data,
        restart_dhu=args.restart_dhu,
        save_snapshot=args.save_snapshot,
    )
    resp = stubs["install_apk"](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def _cmd_snapshot_op(stubs, args, *, verb, stub_key, req_cls):
    """Shared implementation for save-snapshot and load-snapshot commands."""
    req = req_cls(name=args.name, snapshot_name=args.snapshot_name)
    print(f"{verb} snapshot '{args.snapshot_name}' for '{args.name}'...")
    resp = stubs[stub_key](req, timeout=args.timeout)
    print("OK")
    _print_instance(resp.instance)


def cmd_save_snapshot(stubs, args):
    _cmd_snapshot_op(
        stubs, args, verb="Saving", stub_key="save_snapshot",
        req_cls=instance_manager_pb2.SaveSnapshotRequest,
    )


def cmd_load_snapshot(stubs, args):
    _cmd_snapshot_op(
        stubs, args, verb="Loading", stub_key="load_snapshot",
        req_cls=instance_manager_pb2.LoadSnapshotRequest,
    )


def cmd_adb(stubs, args):
    pb = instance_manager_pb2
    req = pb.AdbShellRequest(
        name=args.name,
        args=args.shell_args,
        timeout_s=args.timeout,
    )
    resp = stubs["adb_shell"](req, timeout=args.timeout + 5)
    if resp.stdout:
        sys.stdout.write(resp.stdout)
    if resp.stderr:
        sys.stderr.write(resp.stderr)
    sys.exit(resp.exit_code)


def cmd_push(stubs, args):
    pb = instance_manager_pb2
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
    pb = instance_manager_pb2
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


def main():
    parser = argparse.ArgumentParser(description="Instance manager CLI")
    parser.add_argument("--addr", default="localhost:50061", help="gRPC server address")
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

    p_install = sub.add_parser("install-apk")
    p_install.add_argument("--name", required=True)
    p_install.add_argument("--apk", required=True, help="Path to APK file")
    p_install.add_argument("--restart-dhu", action="store_true", default=True,
                           help="Restart DHU after install (default: true)")
    p_install.add_argument("--no-restart-dhu", dest="restart_dhu", action="store_false",
                           help="Skip DHU restart after install")
    p_install.add_argument("--save-snapshot", default="",
                           help="Save emulator snapshot with this name after install")
    p_install.add_argument("--timeout", type=int, default=180)

    p_save_snap = sub.add_parser("save-snapshot")
    p_save_snap.add_argument("--name", required=True)
    p_save_snap.add_argument("--snapshot-name", required=True,
                             help="Name for the saved snapshot")
    p_save_snap.add_argument("--timeout", type=int, default=180)

    p_load_snap = sub.add_parser("load-snapshot")
    p_load_snap.add_argument("--name", required=True)
    p_load_snap.add_argument("--snapshot-name", required=True,
                             help="Name of the snapshot to load/restore")
    p_load_snap.add_argument("--timeout", type=int, default=180)

    p_adb = sub.add_parser("adb")
    p_adb.add_argument("--name", required=True)
    p_adb.add_argument("--timeout", type=int, default=30)
    p_adb.add_argument("shell_args", nargs="+", metavar="arg", help="adb shell command + args")

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
        "save-snapshot": cmd_save_snapshot,
        "load-snapshot": cmd_load_snapshot,
        "adb": cmd_adb,
        "adb-push": cmd_push,
        "adb-pull": cmd_pull,
    }
    try:
        dispatch[args.command](stubs, args)
    except grpc.RpcError as e:
        print(f"ERROR: {e.code()} — {e.details()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
