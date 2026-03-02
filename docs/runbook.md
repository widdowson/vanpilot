# VanPilot Operational Runbook

How to start, operate, and troubleshoot the VanPilot system.

## Architecture Recap

```
Mac Studio (Docker)              Tailscale tunnel              Pixel 10 Pro
┌────────────────────────┐           │            ┌──────────────────────┐
│ supervisor (gRPC:50051)│◄──────────┼───────────►│ VanPilot Android App │
│ MCP server (stdio)     │           │            │ (gRPC client+server) │
│ Claude Code agents     │           │            └──────────┬───────────┘
│ (tmux sessions)        │           │                       │ AA projection
└────────────────────────┘           │            ┌──────────┴───────────┐
                                     │            │ Head Unit (untrusted)│
                                     │            └──────────────────────┘
```

All server-side components (supervisor, MCP, agents) run in Docker on the Mac Studio. The Android app connects over Tailscale.

## Pre-flight Checklist

Before starting VanPilot, verify:

- [ ] **Mac Studio** is powered on and accessible via SSH or local terminal
- [ ] **Docker** is running: `docker info` succeeds
- [ ] **Tailscale** is active on Mac Studio: `tailscale status` shows the machine as online
- [ ] **Tailscale** is active on Pixel 10 Pro: Tailscale app shows connected
- [ ] Both devices are on the same tailnet and can reach each other: `ping <pixel-tailscale-ip>`
- [ ] **Bazel** is installed: `bazel version` succeeds (needed for builds, not runtime)
- [ ] **Android SDK** is installed (for emulator/DHU development mode): `adb version` succeeds

## Starting the System (Production)

### 1. Build the Docker images

From the repo root on the Mac Studio:

```bash
cd ~/src/vanpilot  # or wherever the repo lives
docker compose build
```

This builds:
- `supervisor` — gRPC server (port 50051), tmux, proto stubs
- `mcp` — MCP display-control server (stdio, for build verification)
- `agent` — Claude Code agent container with tmux

### 2. Start the services

```bash
docker compose up -d
```

The startup order is enforced by `depends_on`:
1. **supervisor** starts first, serves gRPC on port 50051
2. **supervisor healthcheck** passes (gRPC channel ready)
3. **agent** starts, creates a tmux session (`vanpilot-lead`)

The MCP server is not started as a long-running service — it is spawned by Claude Code agents on demand via `.mcp.json`.

### 3. Verify services are healthy

```bash
# Check all containers are running:
docker compose ps

# Check supervisor health:
docker compose logs supervisor | tail -5
# Should show: "Supervisor gRPC server listening on port 50051"

# Check agent tmux session:
docker compose exec agent tmux list-sessions
# Should show: vanpilot-lead

# Test gRPC connectivity:
python -c "
import grpc
ch = grpc.insecure_channel('localhost:50051')
grpc.channel_ready_future(ch).result(timeout=5)
print('Supervisor gRPC: OK')
"
```

### 4. Install and launch the Android app

Build the APK (if not already built):

```bash
bazel build //android:vanpilot
```

Install on the Pixel 10 Pro (connected via USB or ADB over Tailscale):

```bash
adb install -r bazel-bin/android/vanpilot.apk
```

The app starts automatically when Android Auto connects to the head unit.

### 5. Verify end-to-end connectivity

On the Pixel, open the VanPilot app. It should:
- Connect to the supervisor at the configured Tailscale address
- Show "Connected" status (no disconnect indicator in the tab bar)
- Display any pending events from the supervisor

## Starting Development Mode (Emulator + DHU)

For local development without the Pixel or head unit.

### 1. Start the Android emulator

```bash
emulator -avd vanpilot_test &

# Wait for boot:
adb wait-for-device
adb shell getprop sys.boot_completed  # Returns "1" when ready
```

### 2. Start the Desktop Head Unit (DHU)

```bash
# Using the helper script:
scripts/dhu.sh start

# Verify:
scripts/dhu.sh status
# Should show: DHU running (pid NNNNN)
```

The DHU simulates the Android Auto display. It connects to the emulator over ADB port forwarding (tcp:5277).

### 3. Install and run the app in the emulator

```bash
bazel build //android:vanpilot
adb install -r bazel-bin/android/vanpilot.apk
```

The app should appear on the DHU display.

### 4. Run the supervisor locally (optional)

For testing gRPC communication without Docker:

```bash
python -c "
from supervisor.src.server import create_server
server, port, bridge = create_server(50051)
server.start()
print(f'Supervisor listening on port {port}')
server.wait_for_termination()
"
```

## Common Operational Tasks

### Restart an agent session

```bash
# Kill the existing tmux session:
docker compose exec agent tmux kill-session -t vanpilot-lead

# Start a new one:
docker compose exec agent tmux new-session -d -s vanpilot-lead 'exec bash'
```

### View agent tmux output

```bash
# Attach to the agent's tmux session (read-only):
docker compose exec agent tmux attach-session -t vanpilot-lead -r

# Detach with: Ctrl-b d
```

### Check supervisor logs

```bash
# Live logs:
docker compose logs -f supervisor

# Last 50 lines:
docker compose logs --tail 50 supervisor
```

### Check watchdog status

The supervisor's `Watchdog` monitors agent tmux sessions for activity. If an agent goes silent for 60 seconds (configurable), a `WatchdogTimeout` event is emitted and forwarded to the Android app.

To verify watchdog is working, check the supervisor logs for watchdog events.

### Capture a golden screenshot

See [docs/golden-test-guide.md](golden-test-guide.md) for the full golden test workflow. Quick reference:

```bash
# Capture from a running emulator:
python goldens/capture_emulator.py \
  --native \
  --apk bazel-bin/android/vanpilot.apk \
  --output-dir goldens/phase9 \
  --name my_screenshot

# Capture the DHU window on macOS:
scripts/capture_dhu.sh /tmp/dhu_screenshot.png

# Capture via DHU command pipe:
scripts/dhu.sh screenshot /tmp/dhu_screenshot.png
```

### Run golden tests

```bash
# Unit-level golden tests (no emulator):
bazel test //goldens:solid_color_surface_test
bazel test //goldens:golden_diff_test

# Emulator-based golden test (requires running emulator):
bazel test //goldens:emulator_golden_test
```

### Rebuild and redeploy

```bash
# Rebuild Docker images after code changes:
docker compose build
docker compose up -d

# Rebuild and reinstall APK:
bazel build //android:vanpilot
adb install -r bazel-bin/android/vanpilot.apk
```

### Send a test event to the Android app

Use the MCP bridge to inject a display command (from within the supervisor container or a test script):

```python
from supervisor.src.server import create_server

server, port, bridge = create_server(50051)
server.start()

# Submit a bitmap:
with open("test_image.png", "rb") as f:
    image_data = f.read()
bridge.on_bitmap_submitted("0xDEADBEEF", image_data)

# Display it:
bridge.on_display_requested("0xDEADBEEF")
```

## Instance Manager (Automated Emulator Management)

For CI and multi-instance development, the emulator instance manager provides programmatic control over emulator+DHU pairs. See [docs/emulator-instance-manager.md](emulator-instance-manager.md) for the full design.

### Start the instance manager

```bash
bazel run //instance_manager:instance_manager -- --grpc-port 50061 --http-port 8080
```

### Web dashboard

Open `http://localhost:8080` in a browser to see all running instances with live screenshots.

### Create an instance programmatically

```bash
# Via gRPC (from a sandbox worker or test script):
grpcurl -plaintext localhost:50061 vanpilot.v1.InstanceManagerService/CreateInstance \
  -d '{"name": "test-1", "avd_name": "vanpilot_pixel9pro_api36", "snapshot_name": "aa_ready"}'
```

## Shutdown

### Stop Docker services

```bash
docker compose down
```

This stops all containers (supervisor, MCP, agent) gracefully.

### Stop the DHU (development mode)

```bash
scripts/dhu.sh stop
```

### Stop the emulator (development mode)

```bash
adb emu kill
```

### Stop the instance manager

```bash
# Kill the instance manager process (Ctrl-C or SIGTERM)
# It will NOT automatically clean up running emulators.
# Clean up manually:
pkill -f "emulator.*vanpilot"
pkill -f "desktop-head-unit"
```

## Troubleshooting

### Supervisor won't start

**Symptom**: `docker compose up` fails for the supervisor service.

**Check**:
- `docker compose logs supervisor` for error messages
- Port conflict: `lsof -i :50051` — another process may be using the port
- Build error: `docker compose build supervisor` to see build output

### Android app can't connect to supervisor

**Symptom**: App shows disconnect indicator, conversation tabs are empty.

**Check**:
- Tailscale is running on both devices: `tailscale status`
- Supervisor is accessible: from the Pixel, `ping <mac-studio-tailscale-ip>`
- gRPC port is open: `nc -zv <mac-studio-tailscale-ip> 50051`
- Docker is exposing the port: `docker compose ps` shows `0.0.0.0:50051->50051/tcp`

### DHU won't connect to emulator

**Symptom**: `scripts/dhu.sh start` times out.

**Check**:
- Emulator is running: `adb devices` shows `emulator-5554 device`
- AA port forwarding is active: `adb forward --list` should show `tcp:5277 tcp:5277`
- Re-forward: `adb forward tcp:5277 tcp:5277`
- Check DHU logs: `cat /tmp/dhu.log`

### Agent tmux session is gone

**Symptom**: `docker compose exec agent tmux list-sessions` shows no sessions.

**Fix**: Recreate the session:
```bash
docker compose exec agent tmux new-session -d -s vanpilot-lead 'exec bash'
```

### Golden test fails with "No emulator available"

**Check**: `adb devices` shows an emulator in `device` state. If using TCP mode, set `EMU_HOST` and `EMU_PORT` environment variables.

### Emulator takes too long to boot

- Use a snapshot-based AVD for fast boot (< 10s vs 60s+ cold boot)
- Create an `aa_ready` snapshot: boot emulator, install APK, start DHU, verify AA is connected, save snapshot
- Pass `--snapshot aa_ready` to the emulator or use the instance manager's default

### Container resource limits

Per DESIGN.md, resource limits are mandatory:

| Service | CPU | Memory |
|---|---|---|
| supervisor | 2.0 | 1G |
| mcp | 1.0 | 512M |
| agent | 4.0 | 4G |

If agents are slow or OOM-killed, check `docker stats` and adjust limits in `docker-compose.yml` as needed. Do not remove limits entirely.
