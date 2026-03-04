# DHU Video Capture Research

Issue: [#91](https://github.com/widdowson/vanpilot/issues/91)

## Problem Statement

Golden test diagnostics currently capture video of the **emulator phone screen** via `adb shell screenrecord`. This records the Android OS display, not the Android Auto head unit surface rendered by the Desktop Head Unit (DHU). For debugging golden screenshot failures, we need video of what the DHU is actually rendering.

## Current Infrastructure

### DHU Screenshots (existing)

The instance manager already supports DHU screenshots via a named-pipe console command:

```python
# instance_manager/src/emulator_lifecycle.py
pipe_write(pipe_path, f"screenshot {screenshot_path}")
# Then poll filesystem until the PNG appears (0.2s intervals, 5s timeout)
```

- **RPC**: `ScreenshotInstance` returns `dhu_screenshot_png` bytes
- **Latency**: ~200-400ms per capture (pipe write + DHU render + file poll)
- **Background refresh**: Every 30s for the dashboard thumbnails

### Emulator Video (existing)

`goldens/video_capture.py` wraps `adb shell screenrecord`:

- Captures the phone screen (not DHU surface)
- Fixed duration recording (default 5s)
- Enabled via `--record-video` test flag
- Disabled by default, zero overhead when off

## Approaches Investigated

### 1. DHU Console Commands

**Result: No built-in video recording.**

The DHU console (documented at [developer.android.com](https://developer.android.com/training/cars/testing/dhu)) provides exactly one capture command:

```
screenshot filename.png
```

There is no `screenrecord`, `startrecording`, `streamvideo`, or equivalent. The full command set covers input simulation (tap, dpad, keycode), sensors, day/night mode, focus, and restrictions — but no video streaming or recording.

The DHU binary itself has no relevant flags beyond `--headless` and `--config`.

**Verdict**: Cannot use DHU natively for video capture.

### 2. Screenshot Polling + ffmpeg

**Result: Feasible. Recommended approach.**

Rapidly poll DHU screenshots via the existing pipe command and stitch frames into a video with ffmpeg.

**Implementation sketch**:
```
Background thread:
  loop at target FPS:
    pipe_write(pipe, f"screenshot /tmp/dhu_{name}_frame_{n:06d}.png")
    poll for file (up to 300ms)
    n++

On stop:
  ffmpeg -framerate {actual_fps} -i /tmp/dhu_{name}_frame_%06d.png \
         -c:v libx264 -pix_fmt yuv420p output.mp4
```

**Measured/estimated performance**:

| Metric | Value |
|--------|-------|
| DHU screenshot latency | ~200-400ms |
| Achievable FPS | 2-4 FPS |
| Disk I/O per frame | ~200-500KB PNG |
| ffmpeg stitch time | <2s for 30 frames |

**Pros**:
- Works with existing DHU interface — no binary modifications
- Captures exactly what the DHU renders (the actual AA surface)
- Cross-platform (works wherever DHU runs)
- Integrates naturally with instance manager gRPC
- Can reuse the existing `screenshot_to_bytes()` method

**Cons**:
- Low frame rate (2-4 FPS) — adequate for diagnostics, not smooth video
- Filesystem churn from temporary PNGs (mitigated by tmpfs/cleanup)
- Each frame costs a pipe write + file poll cycle

**Verdict**: Best balance of feasibility and value. 2-4 FPS is sufficient for diagnosing golden test failures — we need to see what UI state the DHU was in, not produce cinematic video.

### 3. ADB screenrecord

**Result: Wrong surface.**

```bash
adb shell screenrecord /sdcard/video.mp4
```

This captures the **emulator's phone display**, which shows the Android OS home screen / phone UI. The Android Auto rendering happens inside the DHU process on the host machine, not on the emulator's display buffer. The emulator just provides the AA data stream to the DHU over the forwarded TCP connection.

**Verdict**: Already implemented in `goldens/video_capture.py`. Useful as supplementary context (shows what the phone side is doing) but does not capture the DHU surface.

### 4. macOS Window Capture

**Result: Feasible but platform-specific.**

The project already has `scripts/capture_dhu.sh` which finds the DHU window using CoreGraphics and captures it via `screencapture -l <WID>`:

```bash
WID=$(swift -e '
import CoreGraphics
let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as! [[String: Any]]
for w in list {
    let owner = w["kCGWindowOwnerName"] as? String ?? ""
    if owner.lowercased().contains("desktop-head") && h > 100 {
        print(wid); break
    }
}
')
screencapture -x -o -l "$WID" "$OUTPUT"
```

For video, we could use ffmpeg with avfoundation:

```bash
# Capture entire screen (avfoundation cannot target a specific window)
ffmpeg -f avfoundation -i "1:none" -t 10 output.mp4

# Or: loop screencapture at intervals and stitch
while true; do
    screencapture -x -o -l "$WID" "/tmp/frame_$(printf '%06d' $n).png"
    n=$((n+1))
    sleep 0.2
done
```

**Pros**:
- High fidelity — captures the actual window pixels including window chrome
- `screencapture` is fast (~50-100ms per frame)
- Higher achievable FPS than pipe-based screenshot (~5-10 FPS)

**Cons**:
- macOS only — won't work in Docker containers or Linux CI
- Requires GUI session (no headless mode)
- DHU must run with a visible window (`--headful` mode)
- avfoundation captures full displays, not individual windows; crop coordinates are fragile
- Swift dependency for window ID lookup

**Verdict**: Good for local development diagnostics but not viable for automated/CI use. The instance manager runs on macOS (Mac Studio), so this could work for production, but the DHU pipe approach (Approach 2) is more portable and integrates better with gRPC.

## Recommendation

**Use Approach 2: Screenshot polling + ffmpeg** for the gRPC implementation.

### Rationale

1. **Captures the right surface**: DHU screenshot shows exactly what Android Auto renders, which is what golden tests compare against.
2. **Works with existing infrastructure**: Reuses the proven `screenshot_to_bytes()` pipe mechanism.
3. **gRPC-native**: Fits naturally as `StartVideoCapture` / `StopVideoCapture` RPCs on the instance manager.
4. **Platform-independent**: Works wherever the DHU runs (macOS, Linux).
5. **Adequate quality**: 2-4 FPS is sufficient for diagnostic video — we're debugging UI state transitions, not rendering smooth animations.

### Proposed gRPC API

```protobuf
rpc StartVideoCapture(StartVideoCaptureRequest) returns (StartVideoCaptureResponse);
rpc StopVideoCapture(StopVideoCaptureRequest) returns (StopVideoCaptureResponse);

message StartVideoCaptureRequest {
  string name = 1;           // Instance name
  int32 target_fps = 2;      // Target FPS (default 2, max 5)
  int32 max_duration_s = 3;  // Auto-stop after N seconds (default 30)
}

message StartVideoCaptureResponse {
  string capture_id = 1;     // Unique ID for this capture session
}

message StopVideoCaptureRequest {
  string name = 1;
  string capture_id = 2;
}

message StopVideoCaptureResponse {
  bytes video_mp4 = 1;       // Stitched MP4 video
  int32 frame_count = 2;     // Number of frames captured
  float actual_fps = 3;      // Achieved frame rate
  int32 duration_ms = 4;     // Total capture duration
}
```

### Implementation Plan

1. **Background capture thread**: On `StartVideoCapture`, spawn a daemon thread that loops:
   - Send `screenshot` command to DHU pipe
   - Poll for PNG file, read bytes
   - Store frame in memory or write to numbered temp files
   - Sleep to maintain target FPS (accounting for capture latency)
   - Auto-stop after `max_duration_s`

2. **ffmpeg stitching**: On `StopVideoCapture`:
   - Stop the capture thread
   - Run ffmpeg to stitch frames: `ffmpeg -framerate {fps} -i frame_%06d.png -c:v libx264 -pix_fmt yuv420p output.mp4`
   - Return MP4 bytes in the response
   - Clean up temp files

3. **Resource limits**:
   - Max 1 concurrent capture per instance
   - Auto-stop safety timer (default 30s, configurable)
   - Frame buffer size limit to prevent memory exhaustion

### Optional Enhancement: macOS Window Capture

For local development, `capture_dhu.sh` can be extended to record video via repeated `screencapture` calls. This provides higher FPS (~5-10) but is macOS-specific and not suitable for gRPC integration. It can remain a developer convenience script.
