# VanPilot Design Document

## 1. System Overview

VanPilot enables a user driving a van (or any vehicle) to interact with a team of Claude Code agents running on a remote Mac Studio, using voice commands through an Android Auto head unit. The system is designed for a six-week cross-US RV trip but is architected generically so that any Claude Code agent team mission can be plugged in.

## 2. Components

### 2.1 Mac Studio — Compute Engine

The Mac Studio (24-core, located at the user's home/business) runs all compute-intensive workloads. It hosts:

- **Claude Code Agent Team**: Multiple Claude Code TUI instances running inside tmux sessions within a Docker container. The experimental `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` flag is enabled. Agents run in `--accept-all` mode (full autonomy, no manual approval required). One instance is the team lead; others are specialized teammates. The team lead orchestrates work via Claude Code's built-in inter-agent messaging and shared task list.

- **Supervisory Process**: A long-running process (also inside Docker) that:
  - Tails the JSON conversation logs of all Claude Code TUI instances to extract new agent output.
  - Injects user prompts into the lead agent's tmux session (via `tmux send-keys` or, if feasible, by spoofing the Claude Code inter-agent protocol to appear as a teammate).
  - Tracks what bitmap cache keys the Android app currently holds.
  - Monitors agent health (watchdog) and emits `WatchdogTimeout` events if a session goes silent.
  - Serves the gRPC API that the Android app connects to.

- **MCP Server for Display Control**: An MCP server that the lead agent (and potentially a rendering sub-agent) can invoke to control what is displayed on the Android Auto head unit. This MCP lives inside the Docker container alongside the Claude Code instances so that the agents can reference it natively.

### 2.2 Pixel 10 Pro — Trusted Client

The Pixel 10 Pro runs the VanPilot Android app and is the only device with credentials, internet access, and Tailscale connectivity. It connects to the Mac Studio via Tailscale tunnel.

The Android app is responsible for:

- **Rendering**: Displaying agent output on the Android Auto head unit. The primary display is a tab-based interface where one tab shows the latest visual bitmap card and other tabs show text conversation feeds from the team lead and individual sub-agents.
- **Voice I/O**: On-device speech-to-text (STT) captures the user's voice commands. On-device text-to-speech (TTS) reads back agent responses. No cloud APIs are used for STT/TTS to avoid costs and latency.
- **gRPC Communication**: Bidirectional gRPC with the Mac Studio supervisor. The Android app pulls timestamped events (text messages, display commands, watchdog alerts) and the Mac Studio can push requests (screenshot requests, cache queries) to the Android app.
- **Bitmap Cache**: Maintains a local cache of rendered bitmaps keyed by hex tokens. When the lead agent requests display of a cached image, no retransmission is needed. If a key is missing, the app requests the bitmap from the supervisor.
- **Offline Resilience**: Detects network disconnections and enters read-only mode (voice input disabled, last displayed bitmap retained, disconnect indicator in the tab bar). On reconnection, syncs from the last known timestamp.

### 2.3 Head Unit — Untrusted Display

The aftermarket head unit runs an opaque Android OS distribution that has not been forensically audited. It is treated as a dumb, untrusted display. The head unit:

- Runs an Android Auto emulator that receives projected frames from the Pixel.
- Has no internet access and no personal credentials.
- Forwards touch input back to the Pixel via Android Auto.
- Never sees gRPC traffic, API keys, or any sensitive data.

### 2.4 Van Infrastructure (Informational)

- **Starlink Mini**: Roof-mounted, PoE-injected, provides satellite internet.
- **GL.iNet Slate 7**: Wi-Fi 7 router on the other side of the PoE injector. All van devices connect via this router.
- **Odroid**: Runs Home Assistant OS for van smart home automation (lights, temperature, WICAN Pro CAN bus integration). Not in the critical path for VanPilot, but the Android app may optionally poll the WICAN Pro for CAN bus events (e.g., a steering wheel button press to activate/deactivate conversation mode). This integration is deferred and not a launch requirement.

## 3. Communication Protocol (gRPC)

### 3.1 Transport

All communication between the Android app and the Mac Studio supervisor occurs over gRPC, tunneled through Tailscale. Protocol buffers define the message schemas.

### 3.2 Sync Model — Android App Drives

The Android app always initiates sync by requesting events since a specific timestamp:
```
GetEvents(since_timestamp, max_count) → [Event, Event, ...]
```

- `since_timestamp`: Inclusive lower bound. The supervisor returns all events at or after this time.
- `max_count`: Maximum number of events to return. If the response contains exactly `max_count` events, the client knows there may be more and should query again with the timestamp of the last received event.
- **Idempotency**: If a response is lost mid-stream (Starlink drops), the client simply re-issues the same request and gets the same data plus anything new.

### 3.3 Adaptive Batching

The Android app adjusts `max_count` based on connection health:

- **Stable connection** (no recent disconnects): `max_count = 50`
- **Just reconnected**: `max_count = 5`, increasing gradually as successful responses are received.
- **Rationale**: Smaller payloads are less likely to be lost during unstable connectivity and reduce TCP fragmentation risk.

### 3.4 Event Types (oneof)

Each event has a timestamp and a `oneof` payload:

| Type | Description |
|---|---|
| `TextMessage` | Text output from a Claude Code TUI session. Contains the string payload and an identifier for which agent produced it. |
| `DisplayCommand` | Instructs the Android app to show a bitmap by cache key. |
| `BitmapPayload` | A new bitmap being transmitted, with its cache key and image data. |
| `WatchdogTimeout` | The supervisory process suspects an agent (identified by name/id) has become unresponsive. |
| `InputDeliveryFailure` | A user prompt was injected but no corresponding agent response was detected within a timeout. |

### 3.5 Bidirectional Communication

Both sides are gRPC clients and servers:

**Android App → Mac Studio (pull model):**
- `GetEvents(since_timestamp, max_count)` — primary sync mechanism
- `SendUserInput(text, target_agent)` — deliver transcribed voice input
- `GetBitmap(cache_key)` — request a bitmap the app doesn't have cached

**Mac Studio → Android App (push model):**
- `GetCurrentDisplay()` — ask what cache key is currently shown
- `RequestScreenshot()` — get a PNG of what's currently rendered on the Android Auto display
- `QueryCache(keys)` — check which cache keys the app holds

### 3.6 Display MCP Tool

The lead agent (or a rendering sub-agent) invokes the display MCP to control the head unit:
```
display_bitmap(cache_key, blocking=false)
```

- `blocking=false` (default): The MCP immediately returns success and queues a `DisplayCommand` event.
- `blocking=true`: The MCP holds the connection open until the Android app confirms it is displaying the specified cache key.
```
submit_bitmap(image_data) → { cache_key, screenshot }
```

- The agent submits a rendered bitmap. The MCP assigns a cache key, stores it, and returns the key along with a courtesy screenshot showing how it looks on the display (at the correct dimensions). The agent can verify the rendering before issuing `display_bitmap`.
```
get_screenshot() → { screenshot }
```

- Proactively request a screenshot of the current Android Auto display for troubleshooting or verification.

## 4. Agent Input Injection

### 4.1 Primary Method: tmux send-keys

The supervisory process injects user prompts into the lead agent's tmux session:
```bash
tmux send-keys -t <session>:<pane> "user's transcribed text" Enter
```

After injection, the supervisor tails the conversation log for acknowledgment (new output from the agent). If no response appears within a configurable timeout, an `InputDeliveryFailure` event is emitted.

### 4.2 Experimental: Protocol Spoofing

As a research objective, investigate whether the supervisory process can register itself as a teammate in the Claude Code agent teams protocol and send messages directly to agents via inter-agent messaging. This would be cleaner than tmux keystroke injection.

**Decision**: Implement tmux send-keys first. Protocol spoofing is a stretch goal. If spoofing works, it becomes the preferred input path. If not, tmux send-keys remains the fallback.

## 5. Bitmap Rendering and Caching

### 5.1 Rendering Model

The lead agent (or a dedicated rendering sub-agent) generates bitmaps programmatically and submits them via the display MCP. The agent owns the entire visual — layout, palette, content. This avoids markdown-to-screen translation issues.

### 5.2 Cache Protocol

- Each bitmap is assigned a hex cache key (e.g., `0xDEADBEEF`) by the MCP upon submission.
- The Android app maintains a local in-memory cache of bitmaps keyed by these tokens.
- When the agent calls `display_bitmap(key)`, the app checks its cache. If the key exists, it displays immediately. If not, it requests the bitmap via `GetBitmap(key)`.
- The supervisor tracks which keys have been sent to the Android app. On reconnection, the supervisor knows what the app should have cached (minus anything lost during disconnection).

### 5.3 Cache Lifecycle

- Cache entries persist in memory for the duration of the app's runtime.
- The lead agent can instruct the app to invalidate specific keys (e.g., to free memory or replace stale content).
- The agent can flip between cached images (e.g., show the status dashboard, switch to a research montage, switch back) without retransmission.

### 5.4 Nighttime/Contextual Rendering

The user can provide feedback to the lead agent about rendering preferences (e.g., "use a dark palette at night"). The agent may also detect context from CAN bus data (headlights on/off) if that integration is available. Rendering agents should be responsive to such feedback and adjust their bitmap output accordingly.

## 6. Android App UI

### 6.1 Primary Interface (Android Auto Head Unit)

The head unit display is a 13-inch screen shared with Google Maps (~2/3) and Spotify. VanPilot occupies approximately 1/3 of the display.

**Tab Bar**: A row of tabs along one edge of the VanPilot area:
- **Visual Card**: The latest bitmap from the rendering agent.
- **Lead Agent**: Text conversation feed with the team lead.
- **Sub-Agent Tabs**: One tab per active sub-agent, showing their conversation output.
- **Connection Indicator**: An icon in the tab bar area showing connection status (green = connected, red = disconnected). No extra screen real estate consumed.

**Visual Card History**: The user can swipe or tap through previous visual cards (cached bitmaps) without switching tabs.

**Touch Input**: Tab switches and visual card navigation via touch on the head unit. Touch events are forwarded to the Pixel via Android Auto.

### 6.2 Fallback Interface (Phone Screen)

When the user is away from the van (e.g., on a hike with a Bluetooth headset), the Android app provides a minimal phone-native interface:

- Voice input and TTS output (primary interaction mode).
- Text transcript display.
- Markdown table rendering for structured data.
- No elaborate multi-agent tab switching or visual card management.

This interface is an afterthought — functional but minimal.

## 7. Offline Behavior

### 7.1 Detection

The Android app monitors gRPC connectivity to the Mac Studio. If requests fail or timeout, the app transitions to offline/read-only mode.

### 7.2 Read-Only Mode

- Voice input is **disabled** (no queuing of prompts — avoids race conditions where the agent processes stale commands).
- The last displayed bitmap remains on screen.
- The disconnect indicator in the tab bar turns red.
- The user can still browse cached bitmaps and text history via tab navigation.

### 7.3 Reconnection

On reconnection, the app resumes sync from its last known timestamp using the standard `GetEvents` call. Adaptive batching starts conservatively (small `max_count`) and increases as connection stability is confirmed.

## 8. Watchdog and Error Handling

### 8.1 Agent Watchdog

The supervisory process monitors each Claude Code tmux session for output activity. If a session produces no new output for a configurable timeout period, a `WatchdogTimeout` event is emitted with the agent's identifier.

### 8.2 Input Delivery Verification

After injecting a user prompt via tmux send-keys, the supervisor watches for new output in the conversation log. If no output appears within a timeout, an `InputDeliveryFailure` event is emitted. The Android app can then alert the user that their message may not have been delivered.

### 8.3 Team Lead Failure

If the team lead becomes unresponsive, the user must manually intervene (e.g., SSH into the Mac Studio and restart the tmux session). The supervisory process can alert the user but cannot autonomously recover the lead agent without risking state corruption.

## 9. Security

### 9.1 Head Unit Isolation

The head unit is treated as untrusted. It never receives:
- API keys or credentials
- gRPC traffic
- Tailscale configuration
- Any data beyond Android Auto display frames

### 9.2 Tailscale Tunnel

All gRPC traffic between the Pixel and Mac Studio is encrypted via Tailscale. No ports are exposed to the public internet.

### 9.3 Docker Sandboxing

Claude Code agents run in Docker containers with resource limits (CPU, memory, disk). Agents operate in `--accept-all` mode but are sandboxed. Docker resource limits serve as the blast radius control.

## 10. Local Development Environment

All development and testing occurs on the Mac Studio:

- **Android Studio Emulator**: Emulates the Pixel 10 Pro running the VanPilot app.
- **Android Auto Desktop Head Unit (DHU)**: Google's official tool for emulating an Android Auto head unit. The VanPilot app running in the Android emulator projects to the DHU.
- **Docker**: The supervisor and Claude Code agents run in Docker, same as production.
- **Tailscale**: In local dev, the Android emulator and Docker containers communicate over localhost or a local Tailscale network.

This setup allows end-to-end testing without the physical van.