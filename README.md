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

- **No real Android Auto testing**: Development relies on the Desktop Head Unit (DHU) emulator; no testing on actual vehicle head unit hardware
- **NavigationTemplate is root (no tabs)**: `SurfaceCallback` surface is invisible in DHU screenshots when inside `TabTemplate`, forcing `NavigationTemplate` as root. Conversation tabs are removed; pushed-screen navigation is not yet implemented.
- **Instance manager complexity**: The emulator instance management system is elaborate but tightly coupled to specific Android SDK paths and emulator versions
- **Golden test fragility**: Pixel-exact golden tests are sensitive to emulator version, GPU driver, and display density changes
- **DHU day/night mode stuck**: The DHU `day`/`night` commands don't actually change the Android Auto theme — a DHU emulator limitation
- **Stale branches and worktrees**: 12+ remote branches from merged PRs not deleted; 3 stale worktrees; 18 stash entries from old work
- **blocking display_bitmap not wired**: `display_bitmap(blocking=true)` code exists but is not connected end-to-end to a real Android app
- **Tailscale not deployed**: Configurable gRPC endpoints exist but actual Tailscale tunnel setup is untested

## Opportunities for Improvement

- **Pushed-screen navigation**: Re-add conversation views (Lead Agent, Sub-Agent) as pushed screens from `NavigationTemplate`, restoring tab-like navigation
- **Branch cleanup**: Delete 12+ stale remote branches, remove 3 stale worktrees, clear 18 stash entries
- **Real vehicle testing**: Test on actual Android Auto head unit hardware to validate touch input and display rendering
- **Bandwidth profiling**: Measure actual Starlink Mini bandwidth consumption during typical agent sessions
- **CI golden test stability**: Containerize golden tests to eliminate environment-dependent pixel differences
- **CI optimization**: Implement PR #113's workflow changes to reduce GitHub Actions minutes (issue #111)
- **Video capture windowing**: Implement AC-4.2 — capture only the last N seconds before golden frame, not entire session

## License

TBD