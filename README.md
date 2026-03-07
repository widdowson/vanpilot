# VanPilot — Remote Claude Code Agent Team Controller for Android Auto

VanPilot is a system for remotely controlling and monitoring [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams) from an Android Auto head unit display, with voice input and text-to-speech output. It is designed for mobile, bandwidth-constrained environments (e.g., an RV with Starlink Mini connectivity).

## Architecture Overview
```
┌─────────────────────────────────────────────────────────┐
│                     MAC STUDIO (Home Base)               │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Docker Container                                │    │
│  │                                                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │    │
│  │  │ Claude   │ │ Claude   │ │ Claude   │  ...    │    │
│  │  │ Code TUI │ │ Code TUI │ │ Code TUI │        │    │
│  │  │ (Lead)   │ │ (Agent2) │ │ (Agent3) │        │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘        │    │
│  │       │ tmux panes  │            │               │    │
│  │  ┌────┴─────────────┴────────────┴───────┐      │    │
│  │  │         Supervisory Process            │      │    │
│  │  │  - Tails conversation logs             │      │    │
│  │  │  - Injects user prompts (tmux/proto)   │      │    │
│  │  │  - Manages bitmap cache state          │      │    │
│  │  │  - Watchdog monitoring                 │      │    │
│  │  │  - Hosts MCP for display control       │      │    │
│  │  └────────────────┬──────────────────────┘      │    │
│  │                   │                              │    │
│  └───────────────────┼──────────────────────────────┘    │
│                      │ gRPC                              │
└──────────────────────┼───────────────────────────────────┘
                       │ Tailscale tunnel
                       │
┌──────────────────────┼───────────────────────────────────┐
│  PIXEL 10 PRO        │                                    │
│  ┌───────────────────┴──────────────────────────┐        │
│  │            VanPilot Android App               │        │
│  │  - gRPC client & server (bidirectional)       │        │
│  │  - On-device STT / TTS                        │        │
│  │  - Bitmap cache with keyed tokens             │        │
│  │  - Tab-based UI (visual card / agent convos)  │        │
│  │  - Offline detection + read-only mode         │        │
│  │  - Adaptive sync with timestamp pagination    │        │
│  └───────────────────┬──────────────────────────┘        │
│                      │ Android Auto projection            │
└──────────────────────┼───────────────────────────────────┘
                       │
┌──────────────────────┼───────────────────────────────────┐
│  HEAD UNIT (Untrusted Android OS)                         │
│  ┌───────────────────┴──────────────────────────┐        │
│  │  Android Auto Emulator (on head unit)         │        │
│  │  - Display only (dumb renderer)               │        │
│  │  - No credentials, no internet access         │        │
│  │  - Touch input forwarded to Pixel             │        │
│  └──────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────┘

Also in the van:
  - Starlink Mini (roof) → PoE injector → GL.iNet Slate 7 Wi-Fi router
  - Odroid running Home Assistant OS (van smart home, WICAN Pro)
```

## Key Design Principles

1. **The head unit is untrusted.** All intelligence, credentials, and network access live on the Pixel 10 Pro. The head unit only receives Android Auto frames.
2. **The Mac Studio is the compute engine.** Claude Code agent teams and the supervisory process run there, not on resource-constrained van hardware.
3. **Bandwidth is precious.** Only text and keyed bitmap references travel over Starlink. Bitmaps are cached on the Android app and referenced by token.
4. **The Android app drives sync.** It requests updates since a timestamp, never "give me more." This makes sync idempotent and resilient to network interruptions.
5. **On-device voice processing.** STT and TTS run locally on the Pixel to avoid API costs and latency.
6. **Test-driven development with golden pixel diffs.** Visual verification via committed golden images is the primary QA mechanism.

## Repository Structure
```
vanpilot/
├── README.md
├── DESIGN.md
├── ACCEPTANCE_CRITERIA.md
├── CLAUDE.md
├── BUILD.bazel
├── MODULE.bazel
├── .bazelversion
├── .bazelrc
├── proto/
│   └── vanpilot/
│       └── v1/
│           ├── BUILD.bazel
│           ├── sync.proto
│           ├── display.proto
│           └── screenshot.proto
├── supervisor/
│   ├── BUILD.bazel
│   ├── src/
│   │   ├── main.py
│   │   ├── tmux_manager.py
│   │   ├── log_tailer.py
│   │   ├── prompt_injector.py
│   │   ├── bitmap_cache_tracker.py
│   │   ├── watchdog.py
│   │   └── grpc_server.py
│   └── tests/
├── android/
│   ├── BUILD.bazel
│   ├── app/
│   │   ├── src/
│   │   │   ├── main/
│   │   │   │   ├── java/...
│   │   │   │   ├── res/
│   │   │   │   └── AndroidManifest.xml
│   │   │   └── test/
│   │   └── BUILD.bazel
│   └── auto/
│       ├── src/
│       └── BUILD.bazel
├── mcp/
│   ├── BUILD.bazel
│   └── src/
│       └── display_mcp.py
├── goldens/
│   ├── README.md
│   └── ...
├── docker/
│   ├── Dockerfile.supervisor
│   └── Dockerfile.mcp
└── .github/
    └── workflows/
        └── ci.yml
```

## Getting Started

### Prerequisites

- Mac Studio (or equivalent) with Docker
- Android Studio (for emulator + Android Auto emulator)
- Bazel
- Tailscale
- Claude Code CLI with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

### Local Development

All development and testing can be done from the Mac Studio using Android Studio's emulators. See [DESIGN.md](./DESIGN.md) for the full local development setup.

## Weaknesses

- **No real Android Auto testing**: Development relies on the Desktop Head Unit (DHU) emulator; no testing on actual vehicle head unit hardware has been done yet.
- **Supervisor is single-client MVP**: The supervisory gRPC server is functional (event store, log tailing, tmux input injection, watchdog, MCP bridge) but currently limited to a single client and has a known thread pool exhaustion issue with 4+ concurrent blocking GetBitmap calls.
- **Golden test fragility**: Pixel-exact golden tests are sensitive to emulator version, GPU driver, and display density changes, requiring careful maintenance of baselines.

## Opportunities for Improvement

- **Physical vehicle testing**: Establish a testing pipeline with real Android Auto head units to validate beyond emulator behavior.
- **Multi-client supervisor support**: Extend the supervisor gRPC server beyond single-client MVP to support multiple concurrent connections.
- **Golden test resilience**: Explore perceptual hashing or fuzzy comparison to reduce golden test sensitivity to rendering differences.
- **Bandwidth profiling**: Profile gRPC bitmap transfer sizes and latency to optimize for real cellular/WiFi conditions in a vehicle.

## License

TBD