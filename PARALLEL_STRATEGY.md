# VanPilot Parallel Development Strategy

**Version:** 2.0
**Date:** 2026-03-01
**Status:** Active

---

## Shared Patterns

For project-agnostic patterns — agent teams, git worktrees, PR lifecycle, reviewer checklist, merge order, memory budget, and lessons learned — see:

> [`sandbox/claude-sandbox/PARALLEL_STRATEGY.md`](sandbox/claude-sandbox/PARALLEL_STRATEGY.md)

This document covers VanPilot-specific parallelism, team roles, coordination concerns, and memory estimates.

---

## Parallelism Summary

Phase details and dependency graph live in [`docs/PLAN.md`](docs/PLAN.md). The table below annotates parallelism only:

| Phase | Workstreams | Parallel? |
|-------|-------------|-----------|
| **1** | Bazel bootstrap | Serial — everything blocks on this |
| **2a/2b/2c** | Proto codegen (Python), Proto codegen (Java/KT), Kotlin toolchain + 3rd-party deps | All three parallel |
| **3/4/5** | Android app skeleton, Supervisor skeleton, MCP server skeleton | All three parallel |
| **6** | Docker setup | Serial — integrates phases 3-5 |
| **7/8/9** | End-to-end gRPC wiring, Voice I/O, Golden test infra | All three parallel |

**Critical path:** 1 -> 2b/2c -> 3 -> 6 -> 7

---

## VanPilot Team Agent Roles

Extends the generic role table from the shared doc.

| Role | Worktree | Scope |
|------|----------|-------|
| **Android agent** | `worktrees/android` | Phase 3 (CarAppService, TabTemplate, SurfaceCallback), Phase 7 (gRPC client wiring), Phase 8 (Voice I/O) |
| **Supervisor agent** | `worktrees/supervisor` | Phase 4 (gRPC server, tmux launcher), Phase 7 (event streaming) |
| **MCP agent** | `worktrees/mcp` | Phase 5 (display_bitmap, submit_bitmap, get_screenshot stubs) |
| **Reviewer** | repo root | Reviews all PRs (see shared checklist + addenda below) |
| **Team lead** | repo root | Coordinates merges, relays messages, spawns/shuts down agents |

Phase 2 (proto codegen, Kotlin toolchain) is serial/foundational and does not require agent teams. Agent teams become relevant starting at Phase 3.

---

## VanPilot Reviewer Checklist Addenda

In addition to the shared reviewer checklist, VanPilot PRs must satisfy:

1. **Golden images** — Any PR that changes Android Auto UI must include golden screenshot diffs. The project owner reviews PRs primarily by examining golden diffs, not by running the emulator.
2. **Fine-grained Bazel targets** — No monolithic test targets. Each test suite must be its own `*_test` target (see `CLAUDE.md` for details).
3. **Proto codegen consistency** — If a PR modifies `.proto` files, verify that generated stubs (Python and Java/Kotlin) are regenerated and consistent.
4. **No Gradle** — Reject any PR that introduces Gradle build files or wraps Gradle in Bazel.

---

## VanPilot-Specific Coordination Concerns

### BUILD.bazel Ownership (instead of database migrations)

In web projects, migration ownership is the key coordination concern. In VanPilot, **BUILD.bazel file ownership** is the equivalent:

- Each workstream owns `BUILD.bazel` files in its directory (`android/`, `supervisor/`, `mcp/`)
- Shared targets (`proto/vanpilot/v1/BUILD.bazel`, root `BUILD`) are modified only during Phase 2, which completes before agent teams start
- If two agents need to modify the same `BUILD.bazel`, coordinate via team lead

### Shared Proto Targets

All Phase 3-5 workstreams consume proto-generated stubs, but none should modify `.proto` files or proto `BUILD.bazel` targets. Phase 2 finalizes the proto layer. If a workstream discovers a missing proto field or RPC method, it must go through the team lead to coordinate the change (to avoid conflicting proto edits across worktrees).

### Bazel Disk Cache

Bazel's disk cache (`~/.cache/bazel`) is shared across worktrees. This is a **benefit**, not a problem — cached build artifacts from one worktree speed up builds in others. No special coordination needed.

### Android Emulator + DHU Resource Footprint

The Android emulator plus Desktop Head Unit (DHU) consumes ~2-3 GB RAM when running. This limits concurrent golden testing:

- Only **one agent at a time** should run the emulator + DHU for golden screenshot capture
- Agents can build and run unit tests in parallel (Robolectric tests don't need the emulator)
- The team lead should serialize golden test runs across agents

---

## VanPilot Memory Budget

### Baseline (no agents spawned)

| Component | Estimated RSS |
|---|---|
| Claude lead process | ~560 MB |
| Claude container overhead | ~290 MB |
| Bazel server (persistent) | ~500 MB |
| Tailscale | ~65 MB |
| **Total baseline** | **~1.4 GB** |
| **Available for agents (12 GB sandbox)** | **~8.6 GB** |

Note: VanPilot's baseline is lighter than web projects (no database, web server, or reverse proxy). However, the Bazel server is persistent and significant.

### Agent Concurrency

Using the shared doc's per-agent estimates (600-800 MB each):

| Available RAM | Max agents (unit tests only) | Max agents (emulator running) |
|---|---|---|
| 8.6 GB | 5 | 3 (emulator takes ~2-3 GB) |
| 6 GB | 3 | 2 |

The emulator + DHU is the biggest memory wildcard. Monitor with `free -h` and `docker stats --no-stream` before and during golden test runs.

---

**Document Owner:** APW + Claude
**Last Updated:** 2026-03-01
