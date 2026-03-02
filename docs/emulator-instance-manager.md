# Emulator + DHU Instance Manager

## 1. Problem

VanPilot sandbox workers need to spin up headless Android emulator + DHU instances on the bare macOS host (Mac Studio) for golden testing, rendering verification, and development. Today this is manual: one emulator, one DHU, managed via ad-hoc scripts (`scripts/dhu.sh`). There is no way to run multiple instances concurrently, no way for a sandbox worker to programmatically create or destroy them, and no dashboard for the project owner to see what's running.

## 2. Solution

A Python gRPC service running on the Mac Studio that lets sandbox workers programmatically create, list, screenshot, and destroy named emulator+DHU pairs. A built-in web UI provides the project owner with a dashboard showing all instances and their screenshots.

The service:
- Manages emulator + DHU lifecycle (start, screenshot, stop)
- Allocates ports automatically so multiple instances coexist
- Exposes a gRPC API for programmatic control by sandbox workers
- Serves an HTTP dashboard for human monitoring
- Runs on the Mac Studio alongside (but outside of) Docker containers

## 3. Non-Goals

- **Tailscale setup**: Sandbox workers handle their own Tailscale configuration. This service binds to `0.0.0.0` and relies on Tailscale ACLs for access control.
- **APK installation**: The `aa_ready` snapshot already has VanPilot installed. If a worker needs a fresh APK, they use `adb install` directly.
- **Emulator image management**: AVDs are pre-created on the Mac. The service uses existing AVDs by name.

## 4. Proto Definition

File: `proto/vanpilot/v1/instance_manager.proto`

```proto
syntax = "proto3";

package vanpilot.v1;

option java_package = "com.vanpilot.proto.v1";
option java_multiple_files = true;

// Manages Android emulator + DHU instance pairs on the macOS host.
// Sandbox workers call this to spin up isolated testing environments.
service InstanceManagerService {
  // Create a new emulator + DHU instance pair.
  rpc CreateInstance(CreateInstanceRequest) returns (CreateInstanceResponse);

  // Destroy an existing instance, killing emulator and DHU processes.
  rpc DestroyInstance(DestroyInstanceRequest) returns (DestroyInstanceResponse);

  // List all known instances and their states.
  rpc ListInstances(ListInstancesRequest) returns (ListInstancesResponse);

  // Get details for a single instance by name.
  rpc GetInstance(GetInstanceRequest) returns (GetInstanceResponse);

  // Capture a DHU screenshot from a running instance.
  rpc ScreenshotInstance(ScreenshotInstanceRequest) returns (ScreenshotInstanceResponse);
}

message CreateInstanceRequest {
  // Human-readable instance name (e.g., "coder-agent-1"). Must be unique.
  string name = 1;

  // true = GUI emulator window, false = headless (default).
  bool headful = 2;

  // AVD to use. Default: "vanpilot_pixel9pro_api36".
  string avd_name = 3;

  // Snapshot to restore on boot. Default: "aa_ready".
  string snapshot_name = 4;
}

message CreateInstanceResponse {
  InstanceInfo instance = 1;
}

message DestroyInstanceRequest {
  string name = 1;
}

message DestroyInstanceResponse {}

message ListInstancesRequest {}

message ListInstancesResponse {
  repeated InstanceInfo instances = 1;
}

message GetInstanceRequest {
  string name = 1;
}

message GetInstanceResponse {
  InstanceInfo instance = 1;
}

message ScreenshotInstanceRequest {
  string name = 1;
}

message ScreenshotInstanceResponse {
  // DHU screenshot as PNG bytes.
  bytes screenshot_png = 1;

  // When the screenshot was captured (milliseconds since epoch).
  int64 captured_at_ms = 2;
}

message InstanceInfo {
  string name = 1;
  InstanceState state = 2;

  // Emulator console port (e.g., 5554).
  int32 emulator_console_port = 3;

  // ADB port (e.g., 5555). Always console_port + 1.
  int32 adb_port = 4;

  // AA forwarded port (e.g., 5277).
  int32 aa_forward_port = 5;

  bool headful = 6;

  // Instance creation time (milliseconds since epoch).
  int64 created_at_ms = 7;

  string avd_name = 8;

  // Most recent DHU screenshot (populated by background refresh loop).
  // Omitted if no screenshot has been taken yet.
  bytes last_screenshot_png = 9;
}

enum InstanceState {
  INSTANCE_STATE_UNSPECIFIED = 0;
  CREATING = 1;
  RUNNING = 2;
  ERROR = 3;
  DESTROYING = 4;
}
```

This follows the existing `vanpilot.v1` package conventions from `sync.proto` and `screenshot.proto`.

## 5. Architecture

### 5.1 Directory Structure

```
instance_manager/
├── BUILD.bazel
├── src/
│   ├── __init__.py
│   ├── server.py                      # gRPC + HTTP server setup, entry point
│   ├── instance_store.py              # Thread-safe instance state management
│   ├── instance_manager_service.py    # gRPC servicer + generic handler
│   ├── emulator_lifecycle.py          # Start/stop/screenshot emulator + DHU
│   ├── port_allocator.py              # Port slot allocation
│   └── web_server.py                  # HTTP status dashboard
└── tests/
    ├── __init__.py
    ├── test_instance_store.py
    ├── test_instance_manager_service.py
    ├── test_emulator_lifecycle.py
    ├── test_port_allocator.py
    ├── test_web_server.py
    └── test_e2e.py
```

### 5.2 Component Overview

```
                         ┌──────────────────────┐
  Sandbox Worker ───────►│  gRPC :50061          │
  (via Tailscale)        │  InstanceManager      │
                         │  Service              │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
  Project Owner  ───────►│  HTTP :8080           │
  (browser)              │  Web Dashboard        │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  InstanceStore        │
                         │  (thread-safe dict)   │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              ┌──────────┐   ┌──────────┐   ┌──────────┐
              │ Instance 0│   │ Instance 1│   │ Instance 2│
              │ emu:5554  │   │ emu:5556  │   │ emu:5558  │
              │ dhu:pipe0 │   │ dhu:pipe1 │   │ dhu:pipe2 │
              └──────────┘   └──────────┘   └──────────┘
```

## 6. Server Setup (`server.py`)

Follows the existing `supervisor/src/server.py` pattern:

```python
def create_server(
    grpc_port: int = 50061,
    http_port: int = 8080,
) -> tuple[grpc.Server, threading.Thread, InstanceStore]:
    """Create and configure the instance manager servers.

    Returns:
        (grpc_server, http_thread, instance_store)
    """
```

- Creates `InstanceStore`, `PortAllocator`, `SubprocessRunner`
- Creates `EmulatorLifecycle` with injected dependencies
- Creates `InstanceManagerServicer` and registers via generic handler
- Creates HTTP dashboard thread
- Starts background screenshot refresh daemon thread

Entry point:

```python
def main():
    server, http_thread, store = create_server()
    server.start()
    server.wait_for_termination()
```

## 7. Instance Store (`instance_store.py`)

Thread-safe dict mapping instance name to `InstanceRecord`:

```python
@dataclass
class InstanceRecord:
    name: str
    state: InstanceState          # maps to proto enum
    emulator_console_port: int
    adb_port: int
    aa_forward_port: int
    headful: bool
    created_at_ms: int
    avd_name: str
    emulator_pid: int | None
    dhu_pid: int | None
    keeper_pid: int | None
    pipe_path: str | None
    log_path: str | None
    last_screenshot_png: bytes | None
    last_screenshot_at_ms: int | None
```

Operations are protected by `threading.Lock`:

- `create(name, ...) -> InstanceRecord` — adds entry in CREATING state, raises if name exists
- `get(name) -> InstanceRecord | None`
- `list_all() -> list[InstanceRecord]`
- `update(name, **kwargs)` — update fields (e.g., state, PIDs, screenshot)
- `remove(name)` — delete entry
- `get_running() -> list[InstanceRecord]` — all instances in RUNNING state

## 8. Port Allocator (`port_allocator.py`)

Assigns port slots to instances. Each slot gets three ports:

```
Slot 0: console=5554, adb=5555, aa_fwd=5277
Slot 1: console=5556, adb=5557, aa_fwd=5278
Slot 2: console=5558, adb=5559, aa_fwd=5279
...
Slot N: console=5554+2N, adb=5555+2N, aa_fwd=5277+N
```

```python
@dataclass
class PortSlot:
    slot_index: int
    console_port: int   # 5554 + 2 * slot_index
    adb_port: int       # console_port + 1
    aa_forward_port: int  # 5277 + slot_index

class PortAllocator:
    def allocate() -> PortSlot       # finds lowest free slot
    def release(slot_index: int)     # marks slot available
```

Protected by its own `threading.Lock`. Maximum slots configurable (default 8, matching Mac Studio core count).

## 9. Emulator Lifecycle (`emulator_lifecycle.py`)

Manages the subprocess calls for starting/stopping emulator + DHU pairs. All subprocess interaction goes through an injectable `SubprocessRunner` for testability.

### 9.1 SubprocessRunner

```python
class SubprocessRunner:
    """Wrapper around subprocess calls. Override in tests."""

    def run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(args, **kwargs)

    def popen(self, args: list[str], **kwargs) -> subprocess.Popen:
        return subprocess.Popen(args, **kwargs)
```

### 9.2 CreateInstance Flow

`EmulatorLifecycle.create(name, avd, snapshot, headful, ports) -> InstanceRecord`

1. **Clear crash DB**: `rm -rf /tmp/android-$USER/emu-crash-*.db` (prevents stale crash dialogs)
2. **Start emulator**:
   ```
   emulator @{avd} -read-only -port {console_port} -snapshot {snapshot}
     [-no-window if not headful] -no-boot-anim
   ```
   Store PID.
3. **Wait for boot**: Poll `adb -s emulator-{console_port} shell getprop sys.boot_completed` until it returns `"1"`. Timeout: 60s. On timeout, kill emulator and raise.
4. **Forward AA port**: `adb -s emulator-{console_port} forward tcp:{aa_fwd_port} tcp:5277`
5. **Start DHU via named pipe** (same pattern as `scripts/dhu.sh`):
   - `mkfifo /tmp/dhu_{name}_pipe`
   - Keeper process: `(while true; do sleep 3600; done) > pipe &` — store PID
   - DHU: `$ANDROID_HOME/extras/google/auto/desktop-head-unit < pipe > /tmp/dhu_{name}.log 2>&1 &` — store PID
6. **Wait for DHU**: Grep `/tmp/dhu_{name}.log` for `"connected"`. Timeout: 12s.
7. **Initial screenshot**: Send `screenshot /tmp/dhu_{name}_screenshot.png` via pipe, wait for file, read bytes.
8. **Return**: `InstanceRecord` with state=RUNNING, all PIDs, ports, screenshot.

### 9.3 DestroyInstance Flow

`EmulatorLifecycle.destroy(record: InstanceRecord)`

1. Kill DHU process (`kill {dhu_pid}`)
2. Kill keeper process (`kill {keeper_pid}`)
3. Kill emulator: `adb -s emulator-{console_port} emu kill`
4. Remove port forward: `adb -s emulator-{console_port} forward --remove tcp:{aa_fwd_port}`
5. Clean up: remove pipe, log, PID files
6. Release port slot

### 9.4 Screenshot Flow

`EmulatorLifecycle.screenshot(record: InstanceRecord) -> bytes`

1. Remove existing screenshot file if present
2. Write `screenshot /tmp/dhu_{name}_screenshot.png` to pipe
3. Poll for file existence (up to 5s)
4. Read and return PNG bytes

## 10. gRPC Service (`instance_manager_service.py`)

Follows the exact pattern from `supervisor/src/sync_service.py`:

```python
class InstanceManagerServicer:
    def __init__(
        self,
        store: InstanceStore,
        lifecycle: EmulatorLifecycle,
        port_allocator: PortAllocator,
    ) -> None: ...

    def CreateInstance(self, request, context) -> CreateInstanceResponse: ...
    def DestroyInstance(self, request, context) -> DestroyInstanceResponse: ...
    def ListInstances(self, request, context) -> ListInstancesResponse: ...
    def GetInstance(self, request, context) -> GetInstanceResponse: ...
    def ScreenshotInstance(self, request, context) -> ScreenshotInstanceResponse: ...


def add_instance_manager_service_to_server(
    server: grpc.Server,
    store: InstanceStore,
    lifecycle: EmulatorLifecycle,
    port_allocator: PortAllocator,
) -> None:
    servicer = InstanceManagerServicer(store, lifecycle, port_allocator)
    handler = _InstanceManagerGenericHandler(servicer)
    server.add_generic_rpc_handlers([handler])


class _InstanceManagerGenericHandler(grpc.GenericRpcHandler):
    """Maps InstanceManagerService method paths to handler functions."""

    def __init__(self, servicer: InstanceManagerServicer) -> None:
        self._method_handlers = {
            "/vanpilot.v1.InstanceManagerService/CreateInstance":
                grpc.unary_unary_rpc_method_handler(
                    servicer.CreateInstance,
                    request_deserializer=instance_manager_pb2.CreateInstanceRequest.FromString,
                    response_serializer=instance_manager_pb2.CreateInstanceResponse.SerializeToString,
                ),
            # ... one entry per RPC
        }

    def service(self, handler_call_details):
        return self._method_handlers.get(handler_call_details.method)
```

### RPC Behavior

**CreateInstance**:
- Validate name is non-empty and not already in store
- Apply defaults: `avd_name` → `"vanpilot_pixel9pro_api36"`, `snapshot_name` → `"aa_ready"`
- Allocate port slot
- Add CREATING record to store
- Call `lifecycle.create()` (this blocks — emulator boot takes ~25s with snapshot)
- On success: update state to RUNNING, return InstanceInfo
- On failure: update state to ERROR, release port slot, set context.abort with INTERNAL

**DestroyInstance**:
- Look up instance; abort with NOT_FOUND if missing
- Update state to DESTROYING
- Call `lifecycle.destroy()`
- Remove from store, release port slot

**ListInstances**: Return all records from store, converted to proto `InstanceInfo`.

**GetInstance**: Look up by name; abort with NOT_FOUND if missing.

**ScreenshotInstance**:
- Look up instance; abort with NOT_FOUND if missing
- Abort with FAILED_PRECONDITION if not RUNNING
- Call `lifecycle.screenshot()`
- Update `last_screenshot_png` in store
- Return PNG bytes + timestamp

## 11. Web Dashboard (`web_server.py`)

Minimal HTTP server using Python stdlib `http.server.HTTPServer` with `ThreadingHTTPRequestHandler`:

### Routes

| Route | Method | Response |
|---|---|---|
| `GET /` | HTML | Dashboard page listing all instances |
| `GET /instances/{name}/screenshot` | PNG | Latest cached screenshot for instance |
| `GET /api/instances` | JSON | Machine-readable instance list |

### Dashboard HTML (`GET /`)

Auto-refreshes every 5 seconds via `<meta http-equiv="refresh" content="5">`.

For each instance, shows:
- Name, state (with color: green=RUNNING, yellow=CREATING, red=ERROR)
- Ports: console, ADB, AA forward
- Headful/headless flag
- Uptime (computed from `created_at_ms`)
- Thumbnail screenshot (linked to full-size PNG at `/instances/{name}/screenshot`)

No external dependencies. Inline CSS. Functional, not pretty.

### Screenshot Route (`GET /instances/{name}/screenshot`)

Returns `last_screenshot_png` from the instance store with `Content-Type: image/png`. Returns 404 if instance not found or no screenshot available.

## 12. Background Screenshot Refresh

A daemon thread started by `create_server()`:

```python
def _screenshot_refresh_loop(store: InstanceStore, lifecycle: EmulatorLifecycle):
    while True:
        time.sleep(30)
        for record in store.get_running():
            try:
                png = lifecycle.screenshot(record)
                store.update(record.name, last_screenshot_png=png,
                           last_screenshot_at_ms=int(time.time() * 1000))
            except Exception:
                pass  # log and continue; don't crash the refresh loop
```

This keeps the web dashboard screenshots fresh without requiring explicit screenshot RPCs.

## 13. Bazel Build Targets

File: `instance_manager/BUILD.bazel`

One `py_library` per source file, one `py_test` per test file — matching the `supervisor/BUILD.bazel` pattern exactly.

```python
load("@pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

# ============================================================================
# Libraries
# ============================================================================

py_library(
    name = "port_allocator",
    srcs = ["src/port_allocator.py"],
    imports = [".."],
)

py_library(
    name = "instance_store",
    srcs = ["src/instance_store.py"],
    imports = [".."],
    deps = [
        "//proto/vanpilot/v1:instance_manager_py_proto",
    ],
)

py_library(
    name = "emulator_lifecycle",
    srcs = ["src/emulator_lifecycle.py"],
    imports = [".."],
    deps = [
        ":instance_store",
        ":port_allocator",
    ],
)

py_library(
    name = "instance_manager_service",
    srcs = ["src/instance_manager_service.py"],
    imports = [".."],
    deps = [
        ":emulator_lifecycle",
        ":instance_store",
        ":port_allocator",
        "//proto/vanpilot/v1:instance_manager_py_proto",
        requirement("grpcio"),
    ],
)

py_library(
    name = "web_server",
    srcs = ["src/web_server.py"],
    imports = [".."],
    deps = [
        ":instance_store",
    ],
)

py_library(
    name = "server",
    srcs = ["src/server.py"],
    imports = [".."],
    deps = [
        ":emulator_lifecycle",
        ":instance_manager_service",
        ":instance_store",
        ":port_allocator",
        ":web_server",
        requirement("grpcio"),
    ],
)

py_binary(
    name = "instance_manager",
    srcs = ["src/server.py"],
    main = "src/server.py",
    imports = [".."],
    deps = [":server"],
)

# ============================================================================
# Tests (fine-grained: one target per test module)
# ============================================================================

py_test(
    name = "port_allocator_test",
    srcs = ["tests/test_port_allocator.py"],
    main = "tests/test_port_allocator.py",
    imports = [".."],
    deps = [":port_allocator"],
)

py_test(
    name = "instance_store_test",
    srcs = ["tests/test_instance_store.py"],
    main = "tests/test_instance_store.py",
    imports = [".."],
    deps = [
        ":instance_store",
        "//proto/vanpilot/v1:instance_manager_py_proto",
    ],
)

py_test(
    name = "emulator_lifecycle_test",
    srcs = ["tests/test_emulator_lifecycle.py"],
    main = "tests/test_emulator_lifecycle.py",
    imports = [".."],
    deps = [
        ":emulator_lifecycle",
        ":instance_store",
        ":port_allocator",
    ],
)

py_test(
    name = "instance_manager_service_test",
    srcs = ["tests/test_instance_manager_service.py"],
    main = "tests/test_instance_manager_service.py",
    imports = [".."],
    deps = [
        ":emulator_lifecycle",
        ":instance_manager_service",
        ":instance_store",
        ":port_allocator",
        "//proto/vanpilot/v1:instance_manager_py_proto",
        requirement("grpcio"),
    ],
)

py_test(
    name = "web_server_test",
    srcs = ["tests/test_web_server.py"],
    main = "tests/test_web_server.py",
    imports = [".."],
    deps = [
        ":instance_store",
        ":web_server",
    ],
)

py_test(
    name = "e2e_test",
    srcs = ["tests/test_e2e.py"],
    main = "tests/test_e2e.py",
    imports = [".."],
    deps = [
        ":emulator_lifecycle",
        ":instance_manager_service",
        ":instance_store",
        ":port_allocator",
        ":server",
        ":web_server",
        "//proto/vanpilot/v1:instance_manager_py_proto",
        requirement("grpcio"),
    ],
)
```

Proto targets to add to `proto/vanpilot/v1/BUILD.bazel`:

```python
proto_library(
    name = "instance_manager_proto",
    srcs = ["instance_manager.proto"],
)

py_proto_library(
    name = "instance_manager_py_proto",
    deps = [":instance_manager_proto"],
)
```

(Java/gRPC targets not needed — this service is Python-only on the Mac.)

## 14. Test Strategy

All tests run without real emulators or DHU processes. The `SubprocessRunner` abstraction makes this possible.

### 14.1 Unit Tests (no subprocess, no gRPC)

**`test_port_allocator.py`**:
- Allocate first slot → gets console=5554, adb=5555, aa_fwd=5277
- Allocate second slot → gets console=5556, adb=5557, aa_fwd=5278
- Release slot 0, allocate again → reuses slot 0
- Allocate up to max_slots → raises on next allocate
- Release invalid slot → raises

**`test_instance_store.py`**:
- Create instance → retrievable by name
- Create duplicate name → raises
- List empty store → empty list
- List with instances → returns all
- Update fields → reflected in get
- Remove instance → no longer retrievable
- get_running → only RUNNING instances
- Thread safety: concurrent creates don't corrupt state

**`test_emulator_lifecycle.py`**:
- Mock SubprocessRunner, verify `create()` calls emulator with correct args
- Verify boot polling calls `adb ... getprop sys.boot_completed`
- Verify DHU pipe creation (mkfifo, keeper, DHU start)
- Verify AA port forwarding command
- Boot timeout → raises, emulator killed
- DHU connect timeout → raises, all processes killed
- `destroy()` kills DHU, keeper, emulator in order
- `screenshot()` writes command to pipe, reads file

### 14.2 Service Tests (in-process gRPC, mocked lifecycle)

**`test_instance_manager_service.py`**:
- CreateInstance with defaults → lifecycle.create called with correct defaults
- CreateInstance with custom AVD/snapshot → passed through
- CreateInstance duplicate name → ALREADY_EXISTS error
- DestroyInstance existing → lifecycle.destroy called
- DestroyInstance unknown → NOT_FOUND error
- ListInstances → returns all from store
- GetInstance existing → returns info
- GetInstance unknown → NOT_FOUND error
- ScreenshotInstance running → returns PNG bytes
- ScreenshotInstance not running → FAILED_PRECONDITION error

**`test_web_server.py`**:
- GET / → 200 with HTML containing instance names
- GET /instances/{name}/screenshot → 200 with PNG Content-Type
- GET /instances/unknown/screenshot → 404
- GET /api/instances → 200 with JSON list

### 14.3 Integration Test (full gRPC server, mocked subprocess)

**`test_e2e.py`**:
- Start real gRPC server with mocked SubprocessRunner
- Create instance via gRPC client → verify response
- List instances → see the created instance
- Screenshot instance → get PNG bytes
- Destroy instance → verify empty list
- Create → destroy → create with same name → succeeds (slot reuse)

## 15. Tailscale Integration (Future — Not Implemented Here)

For sandbox workers to reach this service:

1. Each sandbox Docker container runs Tailscale (workers implement this themselves)
2. The Mac Studio's Tailscale ACLs remain unchanged — it accepts connections from any tailnet peer as it does today
3. **Worker-side restriction**: VanPilot worker nodes' Tailscale ACLs restrict them so that, of all tailnet siblings, they can only reach the Mac Studio. Workers access the internet directly (not via Tailscale exit node), so no Tailscale egress rules are needed
4. Tailscale ACL tags (e.g., `tag:vanpilot-worker`) can enforce this policy uniformly across all workers — see Tailscale docs on tag-based ACLs
5. The instance manager binds to `0.0.0.0` — Tailscale ACLs on the worker side enforce which peers they can reach
6. Future: add RV tailnet nodes to the worker ACLs so workers can reach a supervisor running on the RV, ADB into the physical head unit, etc.

## 16. Operational Notes

### Starting the Service

```bash
bazel run //instance_manager:instance_manager -- --grpc-port 50061 --http-port 8080
```

Or directly:

```bash
python -m instance_manager.src.server --grpc-port 50061 --http-port 8080
```

### Resource Limits

Each emulator instance uses ~2GB RAM and 2 CPU cores. The Mac Studio (24-core, 192GB) can comfortably run 8 concurrent instances. The default `max_slots=8` in `PortAllocator` reflects this.

### Crash Recovery

The service is stateless — `InstanceStore` is in-memory only. If the service restarts, it loses track of running emulators. Orphaned emulator/DHU processes must be cleaned up manually or via a startup sweep that checks for running `emulator` and `desktop-head-unit` processes.

Future improvement: write instance state to a JSON file on disk and reconcile on startup.

### Logging

Use Python `logging` module. Each emulator's DHU output goes to `/tmp/dhu_{name}.log`. The service logs to stdout (captured by whatever process supervisor runs it).
