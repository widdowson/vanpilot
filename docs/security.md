# VanPilot Security Analysis

## AC-11.1: Head Unit Isolation — Credential and Secret Exclusion

### Threat Model

The aftermarket head unit runs an opaque, unaudited Android OS. It is treated as a **dumb, untrusted display** (DESIGN.md §2.3). The threat is that credentials, API keys, or raw gRPC traffic could leak to the head unit OS, where they could be exfiltrated by malware or a compromised firmware update.

### Architecture Boundary

```
Mac Studio (Docker)          Tailscale          Pixel 10 Pro         AA projection        Head Unit
┌─────────────────┐         ┌─────────┐        ┌──────────────┐      ┌───────────┐       ┌───────────┐
│ Agents (tmux)   │◄──gRPC──┤ tunnel  ├──gRPC──┤ VanPilot App │──AA──┤ AA Host   │──────►│ Display   │
│ Supervisor      │         └─────────┘        │              │      │ (frames)  │       │ (pixels)  │
│ MCP Server      │                            └──────────────┘      └───────────┘       └───────────┘
└─────────────────┘                                   │
                                                 Secrets live here:
                                                 - Tailscale keys
                                                 - Claude API key (in env)
                                                 - gRPC channel config
```

The **Android Auto projection boundary** between the Pixel and head unit is the critical trust boundary. Only rendered frames (pixels) and touch events cross this boundary.

### Data Flow Trace: MCP → Supervisor → Android App → Head Unit

**1. Agent calls `submit_bitmap(image_data)` via MCP**
- MCP handler (`mcp/src/handlers.py:handle_submit_bitmap`) receives base64-encoded PNG bytes
- Computes a hex cache key, stores raw PNG bytes in the module-level `_cache` dict
- Fires event callback → `McpBridge.on_bitmap_submitted(cache_key, image_data)`
- **Data crossing**: PNG image bytes and a hex cache key string. No credentials.

**2. McpBridge creates a `BitmapPayload` event**
- `supervisor/src/mcp_bridge.py:on_bitmap_submitted` creates a `sync_pb2.Event` with `bitmap_payload` containing `cache_key` (string) and `image_data` (bytes)
- Event is added to the `EventStore`
- **Data crossing**: Proto event with image bytes and cache key. No credentials.

**3. Android app pulls events via `GetEvents` RPC**
- `SyncClient.kt:pollEvents()` calls `stub.getEvents(request)` over gRPC
- Receives `Event` messages; `SyncClient.handleEvent()` dispatches by `payloadCase`:
  - `BITMAP_PAYLOAD` → decodes PNG, stores in `BitmapCache` as `Bitmap` object
  - `DISPLAY_COMMAND` → looks up cache key, calls `onDisplayCommand(cacheKey)`
  - `TEXT_MESSAGE` → forwards `agentId` + `content` strings to callback
- `EventProcessor.kt:processEvent()` handles the full event set, including two additional types:
  - `WATCHDOG_TIMEOUT` → creates a `ProcessedAlert` with agent ID and silent-duration text (e.g., "Agent X unresponsive for 5000ms")
  - `INPUT_DELIVERY_FAILURE` → creates a `ProcessedAlert` with attempted-input and target-agent text (e.g., "Failed to deliver '...' to agent Y")
  - These alerts are rendered as text rows in the UI, so only the human-readable alert string crosses the AA boundary — no raw proto fields or internal identifiers beyond what is shown to the user.
- **Data crossing gRPC**: Proto messages containing text strings, PNG bytes, cache keys, timestamps, agent IDs, watchdog alerts, and input-delivery failure details. No credentials or API keys are part of any proto message schema.

**4. Android app renders to Android Auto Surface**
- `VanPilotSurfaceCallback.kt:displayBitmap()` receives a `Bitmap` object and draws it onto the `Surface` via `Canvas.drawBitmap()`
- `VanPilotScreen.kt:buildMessageList()` creates `ListTemplate` rows containing `msg.text` (string) and `msg.sender` (string)
- **Data crossing AA boundary**: Rendered pixels from `Surface.unlockCanvasAndPost()` and templated UI from the Car App Library. The head unit receives only the visual frame — it never sees the underlying data structures, gRPC messages, or network traffic.

### What the head unit receives

| Data | Reaches head unit? | Form |
|---|---|---|
| Rendered bitmap pixels | Yes | AA projected frames (pixels) |
| Text message content | Yes | Car App Library `ListTemplate` rows (rendered text) |
| Watchdog alerts | Yes | Rendered in UI (text) |
| Input delivery failure alerts | Yes | Rendered in UI (text) |
| Bitmap cache keys | No | Internal to app, never rendered to user |
| gRPC traffic | No | Tailscale tunnel terminates at the Pixel |
| Tailscale keys | No | Stored in Pixel's Tailscale app, never exposed |
| Claude API key | No | Only on Mac Studio, inside Docker |
| Supervisor address/port | No | App config, never rendered |
| `.mcp.json` contents | No | Inside Docker container only |
| Docker environment vars | No | Inside Docker container only |

### What the head unit can send

The head unit can only send:
- **Touch events**: X/Y coordinates forwarded via Android Auto to the Pixel's Car App Library, which interprets them as tab selections or action strip button presses
- **Nothing else**: The head unit has no mechanism to inject gRPC calls, read app memory, or access the Pixel's network stack

### Conclusion

**AC-11.1 is satisfied.** No credentials, API keys, or raw gRPC traffic reach the head unit. The Android Auto projection boundary ensures only rendered pixels and touch coordinates cross to the untrusted device. Secrets (Tailscale keys, Claude API key, gRPC configuration) remain on the Pixel and Mac Studio respectively.

---

## AC-13.4: Protocol Spoofing Investigation

### Background

DESIGN.md §4.2 describes an experimental research objective: investigate whether the supervisory process can register itself as a teammate in the Claude Code agent teams protocol and send messages directly to agents, bypassing tmux keystroke injection.

### Current Input Injection Path

The production input path uses `tmux send-keys` (implemented in `supervisor/src/input_injector.py`):

```
User voice → Android STT → SendUserInput RPC → Supervisor →
  tmux send-keys -t vanpilot-lead "text" Enter → Claude Code TUI
```

This works reliably (AC-13.1 ✓) with delivery verification via log file monitoring (AC-13.2 ✓, AC-13.3 ✓).

### Protocol Spoofing Feasibility

Claude Code agent teams use an internal inter-agent messaging protocol. Investigation findings:

**1. Message transport**: Agent teams communicate via the `SendMessage` tool within the Claude Code API. Messages are routed through Anthropic's infrastructure, not via local IPC. A local process cannot inject messages into this channel without valid API credentials and a registered agent identity.

**2. Team membership**: Agents are registered as team members during team creation via the Claude Code CLI. The team configuration (`~/.claude/teams/{team-name}/config.json`) tracks member names and agent IDs. Adding a fake member would require modifying this config before agents start, which is possible but fragile — the file format is internal and subject to change.

**3. Task list manipulation**: The shared task list (`~/.claude/tasks/{team-name}/`) is file-based. A supervisor could write task files to assign work, but this is a one-way communication channel (agents poll for tasks) and doesn't provide the real-time conversational interaction that voice input requires.

**4. stdin injection alternative**: Claude Code TUI reads from stdin. `tmux send-keys` effectively types into the terminal. An alternative would be writing directly to the TUI's stdin file descriptor via `/proc/<pid>/fd/0`, but this requires knowing the PID and has the same fidelity as `tmux send-keys` without the benefit of tmux's session management.

### Security Implications of Spoofing

If protocol spoofing were possible, it would introduce a risk: **a rogue head unit could potentially inject commands into the agent team**. In the current architecture this is mitigated by:

1. **The head unit never has network access to the supervisor.** gRPC traffic flows over Tailscale between the Pixel and Mac Studio. The head unit only receives projected Android Auto frames.

2. **Touch events are constrained.** The head unit can only send touch coordinates, which the Car App Library maps to predefined template actions (tab selection, button presses). There is no free-text input channel from the head unit — voice input comes from the Pixel's microphone and on-device STT, not from the head unit.

3. **The Pixel mediates all input.** Even if a rogue head unit could somehow inject touch events that triggered voice recording, the STT runs on the Pixel and the resulting text goes through `SendUserInput` over Tailscale to the supervisor. The head unit cannot bypass this path.

4. **Docker resource limits bound blast radius.** Even if an attacker could inject arbitrary prompts into an agent, the agents are sandboxed in Docker with CPU and memory limits (4 CPUs, 4GB RAM). They cannot escape the container to access the host.

### Conclusion

**Protocol spoofing is not feasible as a production input path** given the current Claude Code agent teams architecture. The inter-agent messaging protocol requires valid API credentials and registered agent identities that cannot be easily forged by a local process.

**The spoofing risk from the head unit is negligible.** The head unit has no network path to the supervisor, no mechanism to inject free text, and no way to bypass the Pixel's mediation of all input. The existing `tmux send-keys` approach remains the correct and secure input injection method.

**Recommendation**: Do not pursue protocol spoofing. The `tmux send-keys` path is reliable, testable, and well-understood. If Claude Code exposes a documented API for programmatic input in the future, revisit this decision.
