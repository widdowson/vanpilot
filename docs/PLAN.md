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
      └──────────────┘ └─────────┘ └─────────────┘
```

## Parallelism Summary

| Phase | Workstreams | Parallel? |
|-------|-------------|-----------|
| **1** | Bazel bootstrap | Single track — everything blocks on this |
| **2** | Proto codegen (Python), Proto codegen (Java/KT), Kotlin toolchain + 3rd-party deps | All three parallel |
| **3** | Supervisor skeleton, MCP server skeleton, Android app skeleton | All three parallel |
| **4** | Docker setup | Single track — integrates phases 2-3 |
| **5** | End-to-end gRPC wiring, Voice I/O, Golden test infra | All three parallel |

## Critical Path

The longest dependency chain is:

**1 → 2b/2c → 3 → 6 → 7**

Bazel bootstrap → Kotlin proto codegen + 3rd-party deps → Android app skeleton → Docker setup → end-to-end gRPC wiring.

The Android app skeleton (step 3) is the **highest-risk item** because it depends on the Car App Library's `SurfaceCallback` behaving as documented. Proving this early de-risks the entire project.

## Phase Details

### Phase 1: Bazel Bootstrap

Set up the build system foundation. Everything else depends on this.

- `WORKSPACE` file with repository rules
- `rules_android` for Android builds
- `rules_kotlin` for Kotlin compilation
- `rules_proto` / `rules_grpc` for proto codegen (Java, Python)
- `rules_jvm_external` with `maven_install` for 3rd-party JARs/AARs from Maven Central and Google Maven (Car App Library, gRPC Android, Kotlin stdlib, etc.)
- `rules_python` for supervisor and MCP server
- Root `BUILD` file
- Verify `bazel build //...` succeeds (trivially, with no source yet)

### Phase 2a: Proto Codegen (Python)

- `BUILD` file in `proto/vanpilot/v1/` for Python proto generation
- Verify generated Python stubs import cleanly
- Bazel test target that imports generated stubs

### Phase 2b: Proto Codegen (Java/Kotlin)

- `BUILD` file in `proto/vanpilot/v1/` for Java/Kotlin proto + gRPC generation
- Verify generated Java classes compile
- Bazel test target that instantiates a proto message

### Phase 2c: Kotlin Toolchain + 3rd-Party Deps

- `maven_install` with all Android dependencies:
  - `androidx.car.app:app` (Car App Library)
  - `io.grpc:grpc-android`, `io.grpc:grpc-okhttp`, `io.grpc:grpc-stub`, `io.grpc:grpc-kotlin-stub`
  - `org.jetbrains.kotlin:kotlin-stdlib`
  - `org.jetbrains.kotlinx:kotlinx-coroutines-android`
  - Test dependencies: `junit`, `truth`, `robolectric`
- Verify all artifacts resolve
- Minimal Kotlin `java_library` target to confirm toolchain works

### Phase 3: Android App Skeleton

Minimal app that proves the Car App Library + SurfaceCallback approach works.

- `AndroidManifest.xml` declaring navigation category, `NAVIGATION_TEMPLATES` and `ACCESS_SURFACE` permissions
- `CarAppService` subclass
- `Session` subclass returning a `Screen`
- `Screen` returning a `TabTemplate` with one tab
- That tab embeds a `NavigationTemplate` with a `SurfaceCallback`
- `SurfaceCallback.onSurfaceAvailable()` draws a solid color rectangle on the `Canvas`
- Verify it renders in Android emulator + DHU
- Fine-grained Bazel test targets (not one monolithic test)

### Phase 4: Supervisor Skeleton

- Python package under `supervisor/src/`
- gRPC server implementing `SyncService.GetEvents` (returns hardcoded events)
- Basic tmux session launcher (starts a single tmux session)
- Bazel test targets for each module

### Phase 5: MCP Server Skeleton

- Python package under `mcp/src/`
- MCP tool definitions: `display_bitmap`, `submit_bitmap`, `get_screenshot`
- Stub implementations that return mock responses
- `.mcp.json` config file for agent discovery
- Bazel test targets

### Phase 6: Docker Setup

- `docker/Dockerfile.supervisor` — supervisor + Python deps
- `docker/Dockerfile.mcp` — MCP server
- `docker-compose.yml` for local dev (supervisor, MCP, tmux sessions)
- Resource limits on all containers
- Verify supervisor starts and serves gRPC inside Docker

### Phase 7: End-to-End gRPC Wiring

- Android app connects to supervisor over gRPC, pulls events, displays text in `ListTemplate`
- Android app blits a `BitmapPayload` onto the `SurfaceCallback` surface
- Supervisor reverse-calls Android app's `AndroidAppService`
- Integration test with emulator + Docker

### Phase 8: Voice I/O

- Phase 1: Android `SpeechRecognizer` with offline language pack for STT
- `TextToSpeech` for TTS, reading incoming `TextMessage` events aloud
- Voice disabled in offline mode
- Bazel test targets per component

### Phase 9: Golden Test Infrastructure

- Bazel rules to launch Android emulator + Android Auto DHU
- Automate DHU pairing with emulator over adb
- Screenshot capture from DHU surface
- Pixel-by-pixel comparison against committed goldens with configurable tolerance
- Diff image generation on failure
- Optional video capture via `--test_arg=--record-video`
