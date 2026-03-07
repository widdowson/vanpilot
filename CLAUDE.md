# CLAUDE.md — Instructions for Claude Code Agents

This file provides instructions and context for Claude Code agents working on the VanPilot project. Read this file first before making any changes.

## Project Overview

VanPilot is a system for controlling Claude Code Agent Teams from an Android Auto head unit via voice. See README.md for the architecture diagram, DESIGN.md for the full design, and ACCEPTANCE_CRITERIA.md for what "done" looks like.

## Critical Build System Rules

**USE BAZEL NATIVELY. DO NOT WRAP OTHER BUILD SYSTEMS.**

- This project uses Bazel as its sole build system. Use Bazel's native Android rules (`rules_android`, `rules_kotlin` if using Kotlin, `rules_jvm_external` for dependencies).
- Do NOT use Gradle, even as an intermediary. Do NOT create a single Bazel test target that delegates to JUnit or another test framework as a monolithic runner. Each test suite or logical group of tests must be its own Bazel `*_test` target.
- Hermeticity and parallelism are non-negotiable. Bazel's value comes from hermetic, cacheable, parallelizable builds and tests. If your approach defeats any of these properties, you are doing it wrong.
- Do NOT use npm, pip, or any other package manager as a primary dependency mechanism. All dependencies must be declared in Bazel.

**Bad** (one giant test that delegates to another framework):
```python
java_test(
    name = "all_tests",
    srcs = glob(["**/*Test.java"]),
    ...
)
```

**Good** (fine-grained test targets):
```python
java_test(
    name = "bitmap_cache_test",
    srcs = ["BitmapCacheTest.java"],
    ...
)

java_test(
    name = "grpc_sync_test",
    srcs = ["GrpcSyncTest.java"],
    ...
)
```

## Development Methodology

This project follows strict Test-Driven Development (TDD):

1. **Write failing tests first.** Every feature begins with test code that expresses the expected behavior. These tests must fail before the implementation exists.
2. **Write the implementation.** Make the tests pass. Do not write code that is not driven by a test.
3. **Update or add golden images.** If the feature affects UI rendering, update existing golden screenshots or add new ones. The golden diffs in the PR are the owner's primary review mechanism.
4. **Commit structure**: Ideally, PRs show the TDD flow clearly. At minimum, the PR description must state what tests were written and what they cover.

## Golden Image Testing

Golden tests are critical to this project. The project owner reviews PRs primarily by examining golden image diffs rather than manually running the emulator.

- Golden images live in `goldens/` and are committed to the repo.
- When you add a new UI state or feature, you MUST add corresponding golden images.
- When you change existing UI behavior, the golden image diffs MUST be part of the PR.
- Golden tests launch the Android emulator + Android Auto DHU, render the UI, capture a screenshot, and compare pixel-by-pixel against the committed golden.
- If a golden test fails, it produces a diff image highlighting changed pixels.
- **DHU screenshots**: Use `goldens/golden_diff.py:crop_to_app_pane()` to crop away the DHU chrome and status bar. Output should be 1832x1056 (matching existing goldens in `goldens/dhu/`).
- **Phone screenshots**: Use `goldens/golden_diff.py:mask_status_bar()` to blank out the phone status bar with hot pink.
- The visual diff tool for reviewing golden PRs is at `vr.apw.photos/widdowson/vanpilot/pr/{number}`.

## Instance Manager

Agents use the instance manager (gRPC on `mac:50061`) to control emulator + DHU instances. Key rules:

- **Each agent MUST use its own named instance** (e.g., `create --name golden-capturer`). Never use generic names like `test-1`.
- **Use Bazel for the client**: `bazel run //instance_manager:instance_manager_client -- COMMAND`. Do NOT create standalone/vendored client scripts.
- **No pre-baked APKs in snapshots** — always build and install the latest APK via `install-apk`.
- See `docs/agent-instance-manager-guide.md` for full usage and `docs/app-launch.md` for launching VanPilot on the DHU.

## Proto Files

All gRPC message types and services are defined in `proto/vanpilot/v1/`. When adding new event types, RPC methods, or messages, update the proto files first, then regenerate the code.

## Docker

The supervisory process and MCP server run in Docker containers. Dockerfiles live in `docker/`. Claude Code agents also run inside Docker with resource limits. If you need to modify the Docker setup, ensure resource limits remain in place.

## Security Constraints

- The head unit is untrusted. Never send credentials, API keys, or raw gRPC traffic to it.
- All network communication between the Android app and Mac Studio goes through Tailscale.
- Claude Code agents are sandboxed in Docker. Do not remove or weaken resource limits.

## Language

The Android app may be written in Kotlin or Java. The project owner is experienced with Java (though not recently) and open to Kotlin. The supervisory process and MCP server are in Python.

## Key Files

| File | Purpose |
|---|---|
| `README.md` | Architecture overview, repo structure |
| `DESIGN.md` | Detailed design: components, protocols, behavior |
| `ACCEPTANCE_CRITERIA.md` | Checklist of all acceptance criteria |
| `proto/vanpilot/v1/*.proto` | gRPC protocol definitions |
| `goldens/` | Committed golden screenshots |