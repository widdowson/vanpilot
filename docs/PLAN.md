# VanPilot Implementation Plan

This document describes the build-out plan: what needs to be done, what depends on what, and what can be parallelized.

## Dependency Graph

```
                        ┌─────────────────────┐
                        │  1. Bazel Bootstrap  │
                        │  WORKSPACE, rules,   │
                        │  toolchains          │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
          ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
          │ 2a. Proto   │ │ 2b. Proto    │ │ 2c. Kotlin   │
          │ codegen     │ │ codegen      │ │ toolchain +  │
          │ (Python)    │ │ (Java/KT)    │ │ 3rd-party    │
          └──────┬──────┘ └──────┬───────┘ │ deps         │
                 │               │         └──────┬───────┘
        ┌────────┘          ┌────┴────┐           │
        ▼                   ▼         ▼           ▼
 ┌──────────────┐  ┌────────────┐ ┌────────────────────┐
 │ 4. Supervisor│  │ 5. MCP     │ │ 3. Android App     │
 │ skeleton     │  │ server     │ │ skeleton            │
 │ (Python,     │  │ skeleton   │ │ (CarAppService,     │
 │  gRPC server)│  │ (Python)   │ │  TabTemplate,       │
 └──────┬───────┘  └─────┬─────┘ │  SurfaceCallback)   │
        │                 │       └─────────┬───────────┘
        │                 │                 │
        ▼                 ▼                 ▼
 ┌──────────────────────────────────────────────────────┐
 │          6. Docker setup (compose, Dockerfiles)       │
 │          Wires supervisor + MCP + agent containers    │
 └──────────────────────────┬───────────────────────────┘
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
      ┌──────────────┐ ┌─────────┐ ┌─────────────┐
      │ 7. End-to-end│ │ 8. Voice│ │ 9. Golden   │
      │ gRPC wiring  │ │ I/O     │ │ test infra  │
      │ (app↔super↔  │ │ (STT/   │ │ (emulator + │
      │  MCP)        │ │  TTS)   │ │  DHU auto)  │
      └──────┬───────┘ └─────────┘ └─────────────┘
             │
    ─────────┼───────────────────────────────
    Post-skeleton phases (10+)
    ─────────┼───────────────────────────────
             │
        ┌────┴─────────────────┐
        ▼                      ▼
 ┌──────────────┐    ┌──────────────────┐
 │ 10. Log      │    │ 11. Configurable │
 │ tailer       │    │ gRPC endpoint +  │
 │ (supervisor) │    │ Tailscale        │
 └──────┬───────┘    └────────┬─────────┘
        │                     │
        ▼                     ▼
 ┌──────────────────────────────────────────┐
 │ 12. Production Docker (agent container   │
 │     with Claude Code CLI + MCP inside)   │
 └──────────────────────┬───────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
    ┌────────────┐ ┌──────────┐ ┌──────────────┐
    │ 13. E2E    │ │ 14. APK  │ │ 15. Ops      │
    │ smoke test │ │ signing  │ │ runbook      │
    └────────────┘ └──────────┘ └──────────────┘
```

## Status (2026-03-06)

**All 15 phases are complete.** Every phase has at least one merged PR. The project is now in a maintenance/polish phase.

### Remaining Acceptance Criteria (4 items)

| AC | Description | Blocker |
|----|-------------|---------|
| AC-4.2 | Video capture "last N seconds" before golden frame | Implementation gap — capture exists but windowing not built |
| AC-6.3 | `display_bitmap(blocking=true)` end-to-end | Code exists, not wired to real Android app |
| AC-10.2 | Renders correctly on 13-inch head unit | Requires real hardware |
| AC-11.2 | gRPC over Tailscale | Configurable endpoints exist; Tailscale not deployed |

### Architecture Change: NavigationTemplate as Root

As of PR #118, `VanPilotScreen` uses `NavigationTemplate` directly as the root template (not `TabTemplate`). This was required because `SurfaceCallback`'s surface layer is not visible in DHU screenshots when embedded inside `TabTemplate`. Conversation views (Lead Agent, Sub-Agent tabs) are **blocked** pending a pushed-screen implementation.

### Open PRs

| PR | Title | Branch |
|----|-------|--------|
| #119 | docs: comprehensive README update | `docs/readme-update-2026-03-05` |
| #118 | feat: golden screenshots + NavigationTemplate surface fix | `golden-screenshots-capture` |
| #117 | chore: remove standalone client and vendored proto stubs | `cleanup/remove-standalone-client` |
| #113 | ci: optimize workflows | `ci/optimize-workflows-111` |
| #112 | docs: CI optimization plan | `ci/optimization-plan-111` |

### Open Issues

| Issue | Title |
|-------|-------|
| #111 | Optimize GitHub Actions CI — reduce action-minutes usage |
| #110 | pip install fails inside sandbox — proxy MITM cert not trusted by pip |

---

## Parallelism Summary

| Phase | Workstreams | Parallel? | Status |
|-------|-------------|-----------|--------|
| **1** | Bazel bootstrap | Single track — everything blocks on this | **Done** |
| **2** | Proto codegen (Python), Proto codegen (Java/KT), Kotlin toolchain + 3rd-party deps | All three parallel | **Done** |
| **3** | Supervisor skeleton, MCP server skeleton, Android app skeleton | All three parallel | **Done** |
| **4** | Docker setup | Single track — integrates phases 2-3 | **Done** |
| **5** | End-to-end gRPC wiring, Voice I/O, Golden test infra | All three parallel | **Done** |
| **6** | Log tailer, Configurable gRPC + Tailscale | Both parallel (supervisor vs Android) | **Done** |
| **7** | Production Docker setup | Single track — integrates 10 + 11 | **Done** |
| **8** | E2E smoke test, APK signing, Ops runbook | All three parallel | **Done** |

## Critical Path

The longest dependency chain was:

**1 → 2b/2c → 3 → 6 → 7 → 10 → 12 → 13**

All phases on this path are now complete.

## Phase Details

### Phase 1: Bazel Bootstrap ✅

Set up the build system foundation. Everything else depends on this.

- `WORKSPACE` file with repository rules
- `rules_android` for Android builds
- `rules_kotlin` for Kotlin compilation
- `rules_proto` / `rules_grpc` for proto codegen (Java, Python)
- `rules_jvm_external` with `maven_install` for 3rd-party JARs/AARs from Maven Central and Google Maven (Car App Library, gRPC Android, Kotlin stdlib, etc.)
- `rules_python` for supervisor and MCP server
- Root `BUILD` file
- Verify `bazel build //...` succeeds (trivially, with no source yet)

### Phase 2a: Proto Codegen (Python) ✅

- `BUILD` file in `proto/vanpilot/v1/` for Python proto generation
- Verify generated Python stubs import cleanly
- Bazel test target that imports generated stubs

### Phase 2b: Proto Codegen (Java/Kotlin) ✅

- `BUILD` file in `proto/vanpilot/v1/` for Java/Kotlin proto + gRPC generation
- Verify generated Java classes compile
- Bazel test target that instantiates a proto message

### Phase 2c: Kotlin Toolchain + 3rd-Party Deps ✅

- `maven_install` with all Android dependencies:
  - `androidx.car.app:app` (Car App Library)
  - `io.grpc:grpc-android`, `io.grpc:grpc-okhttp`, `io.grpc:grpc-stub`, `io.grpc:grpc-kotlin-stub`
  - `org.jetbrains.kotlin:kotlin-stdlib`
  - `org.jetbrains.kotlinx:kotlinx-coroutines-android`
  - Test dependencies: `junit`, `truth`, `robolectric`
- Verify all artifacts resolve
- Minimal Kotlin `java_library` target to confirm toolchain works

### Phase 3: Android App Skeleton ✅

Minimal app that proves the Car App Library + SurfaceCallback approach works.

- `AndroidManifest.xml` declaring navigation category, `NAVIGATION_TEMPLATES` and `ACCESS_SURFACE` permissions
- `CarAppService` subclass
- `Session` subclass returning a `Screen`
- `Screen` returning a `TabTemplate` with one tab
- That tab embeds a `NavigationTemplate` with a `SurfaceCallback`
- `SurfaceCallback.onSurfaceAvailable()` draws a solid color rectangle on the `Canvas`
- Verify it renders in Android emulator + DHU
- Fine-grained Bazel test targets (not one monolithic test)
- **Golden screenshots**: Capture via `adb shell screencap` and commit to `goldens/`. PR must include visual evidence of the solid-color rectangle rendering on the DHU surface. No automated comparison yet — human reviews the PNG in the PR diff.

### Phase 4: Supervisor Skeleton ✅

- Python package under `supervisor/src/`
- gRPC server implementing `SyncService.GetEvents` (returns hardcoded events)
- Basic tmux session launcher (starts a single tmux session)
- Bazel test targets for each module

### Phase 5: MCP Server Skeleton ✅

- Python package under `mcp/src/`
- MCP tool definitions: `display_bitmap`, `submit_bitmap`, `get_screenshot`
- Stub implementations that return mock responses
- `.mcp.json` config file for agent discovery
- Bazel test targets

### Phase 6: Docker Setup ✅

- `docker/Dockerfile.supervisor` — supervisor + Python deps
- `docker/Dockerfile.mcp` — MCP server
- `docker-compose.yml` for local dev (supervisor, MCP, tmux sessions)
- Resource limits on all containers
- Verify supervisor starts and serves gRPC inside Docker

### Phase 7: End-to-End gRPC Wiring ✅

- Android app connects to supervisor over gRPC, pulls events, displays text in `ListTemplate`
- Android app blits a `BitmapPayload` onto the `SurfaceCallback` surface
- Supervisor reverse-calls Android app's `AndroidAppService`
- Integration test with emulator + Docker
- **Golden screenshots**: Capture and commit goldens showing text displayed in ListTemplate tab and a bitmap blitted onto the Surface via gRPC

### Phase 8: Voice I/O ✅

- Phase 1: Android `SpeechRecognizer` with offline language pack for STT
- `TextToSpeech` for TTS, reading incoming `TextMessage` events aloud
- Voice disabled in offline mode
- Bazel test targets per component
- **Golden screenshots**: Capture and commit goldens showing voice UI states (listening indicator, disabled state in offline mode) if applicable

### Phase 9: Golden Test Infrastructure ✅

Upgrades the manual golden screenshots (committed since Phase 3) into automated Bazel test targets.

- Bazel rules to launch Android emulator + Android Auto DHU
- Automate DHU pairing with emulator over adb
- Screenshot capture from DHU surface
- Pixel-by-pixel comparison against committed goldens with configurable tolerance
- Diff image generation on failure
- Optional video capture via `--test_arg=--record-video`
- Reusable golden tooling may be extracted from `apwphotos-appv2` as a shared submodule

---

## Post-Skeleton Phases

Phases 1–9 build all individual components. Phases 10–15 close the gaps required for a working end-to-end system.

### Phase 10: Log Tailer (#62) ✅ — PRs #73, #77

**Depends on:** Phase 4 (supervisor skeleton), Phase 7 (end-to-end gRPC wiring)

DESIGN.md §2.1 says the supervisor "Tails the JSON conversation logs of all Claude Code TUI instances to extract new agent output." This component is missing. Without it, agent `TextMessage` output never populates the `EventStore`, so the Android app's conversation tabs remain empty.

The `InputInjector` monitors log file growth (size-based) for delivery verification, but does not parse log content.

- Implement `LogTailer` class in `supervisor/src/log_tailer.py`
- Tail JSONL conversation logs for all active tmux sessions
- Parse log entries and create `TextMessage` events in the `EventStore`
- Handle log rotation and agent restarts gracefully
- Bazel test targets for log parsing and event generation
- Integration test: injected prompt → agent log output → `TextMessage` event in store

### Phase 11: Configurable gRPC Endpoint + Tailscale (#65) ✅ — PR #80

**Depends on:** Phase 3 (Android app skeleton), Phase 7 (end-to-end gRPC wiring)

**Parallel with:** Phase 10 (log tailer — different codebase: Android vs supervisor)

AC-11.2 requires all gRPC traffic tunneled through Tailscale. DESIGN.md §3.1 specifies stable Tailscale hostnames (e.g., `mac-studio.tailnet:50051`) with configurable endpoints.

Currently, `SyncClient` and `SyncManager` accept an injected `ManagedChannel` (good design), but no production code constructs one. `VanPilotSession.onCreateScreen()` creates `VanPilotScreen` without a gRPC channel. There is no configuration mechanism for the supervisor address.

- Add configurable gRPC endpoint to the Android app (SharedPreferences or BuildConfig)
- Default to Tailscale hostname convention (`mac-studio.tailnet:50051`)
- Wire `VanPilotSession` to create a `ManagedChannel` and pass it to `SyncManager`
- Configure TLS for Tailscale tunnel (or document why plaintext is acceptable within Tailscale)
- Ensure supervisor listens on `0.0.0.0:50051` (not just localhost) for Tailscale access
- Document Tailscale setup steps for both Mac Studio and Pixel

### Phase 12: Production Docker Setup (#63, #64) ✅ — PR #72

**Depends on:** Phase 10 (log tailer), Phase 11 (configurable gRPC endpoint)

Two gaps combine here:

**Gap A: MCP code not in agent container (#63).** The `.mcp.json` config tells Claude Code to spawn the MCP via `python3 -m mcp.src.server` over stdio. The standalone `mcp` service in `docker-compose.yml` is for build verification only. The `agent` container does not have MCP source code, so Claude Code cannot spawn the MCP server.

**Gap B: Agent container is a placeholder (#64).** The `agent` service uses `python:3.12-slim` with a bare tmux session. It lacks Claude Code CLI, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, the project repo, and startup scripts.

- Install Claude Code CLI in the agent container
- Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Mount or copy the project repo into the container
- Mount or copy MCP source into the agent container so `.mcp.json` works
- Create startup script: launch team lead + configurable teammates in tmux panes with `--accept-all`
- Verify agents can call `display_bitmap` / `submit_bitmap` via MCP
- Maintain resource limits per DESIGN.md §9.3 (4 CPUs, 4GB RAM for agent container)
- Integration test: agent container starts, MCP spawns successfully, display tool call round-trips

### Phase 13: End-to-End Smoke Test (#67) ✅ — PR #78 (instance manager)

**Depends on:** Phase 12 (production Docker setup)

Existing tests cover individual components in isolation (`test_e2e_grpc.py`, `test_e2e_reverse_path.py`, Android unit tests with `InProcessChannelBuilder`). No test exercises the full chain.

- Smoke test script or Bazel test target that starts supervisor + MCP in Docker
- Simulates event flow through the supervisor (mock agent output or scripted tmux input)
- Android emulator connects via gRPC and receives events
- Verifies `TextMessage` appears in conversation tab and/or bitmap renders on surface
- Tagged `manual` (requires emulator + Docker)
- Intended to run in CI using the emulator instance manager (Phase 9 / issue #54)

### Phase 14: APK Signing (#66) ✅ — PR #75

**Depends on:** Phase 3 (Android app skeleton) — can be done any time after Phase 3

**Parallel with:** Phases 10–13

No signing configuration exists for release builds. Only debug builds are possible. To deploy to the Pixel 10 Pro, a signed APK is required.

- Bazel build target for a signed release APK
- Keystore file management (gitignored, documented)
- Signing config uses environment variables or a local properties file (no secrets in repo)
- Document the signing setup for new developers

### Phase 15: Operational Runbook (#68) ✅ — PR #71

**Depends on:** Phases 10–12 (system must be startable to document how to start it)

**Parallel with:** Phase 13 (smoke test), Phase 14 (APK signing)

No documentation exists for how to actually start and operate VanPilot end-to-end.

- `docs/runbook.md` with step-by-step startup instructions
- Pre-flight checklist (Tailscale connected, Docker running, etc.)
- `docker-compose up` workflow
- Android app installation and first-run instructions
- Verification steps (how to confirm each component is healthy)
- Troubleshooting section for common failures
- Shutdown procedure
