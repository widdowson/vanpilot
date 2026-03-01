# Parallel Bootstrap — Wave 1 (Phases 3/4/5)

**Purpose:** Instructions for the team lead agent to launch Wave 1 of VanPilot parallel development using Claude Code Agent Teams. This file is consumed once, at team launch time.

**Prerequisites:**
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` must be set in the environment
- Phases 1, 2a, 2b, 2c are complete (Bazel bootstrap, proto codegen, Kotlin toolchain). Verified via PRs #1-#4.
- The next unblocked work is Phases 3, 4, and 5 — all three are independent and can run in parallel.

---

## What's Done

| Phase | Status | PR |
|-------|--------|----|
| 1. Bazel Bootstrap | Done | #1 |
| 2a. Proto Codegen (Python) | Done | #2 |
| 2b. Proto Codegen (Java/Kotlin) | Done | #3 |
| 2c. Kotlin Toolchain + 3rd-Party Deps | Done | #4 |

All foundational build system work is complete. `bazel build //...` succeeds. Proto stubs generate for both Python and Java/Kotlin. Maven deps resolve. Kotlin toolchain compiles.

## What's Next

Phases 3, 4, and 5 are all unblocked and fully parallel. No shared files between them — each owns its own directory and BUILD.bazel.

---

## Worktree Setup

Run from the repo root before spawning agents:

```bash
# Create feature branches
git checkout -b feature/android-skeleton && git checkout main
git checkout -b feature/supervisor-skeleton && git checkout main
git checkout -b feature/mcp-skeleton && git checkout main

# Create worktrees
mkdir -p worktrees
git worktree add worktrees/android feature/android-skeleton
git worktree add worktrees/supervisor feature/supervisor-skeleton
git worktree add worktrees/mcp feature/mcp-skeleton
```

---

## Team Roster

Create the team with `TeamCreate`, then spawn agents one at a time (cd to the correct worktree before each spawn — see Lesson #1 in `sandbox/claude-sandbox/PARALLEL_STRATEGY.md`).

### Agent: `android`

**Worktree:** `worktrees/android`
**Branch:** `feature/android-skeleton`
**Phase:** 3 (Android App Skeleton)

**Prompt:**
```
You are the android agent for VanPilot. Read CLAUDE.md and docs/PLAN.md first.

Your job is Phase 3: Android App Skeleton. This is the highest-risk phase — it proves whether Car App Library's SurfaceCallback actually works.

Deliverables (TDD — write failing tests first):
1. AndroidManifest.xml declaring navigation category, NAVIGATION_TEMPLATES and ACCESS_SURFACE permissions
2. CarAppService subclass
3. Session subclass returning a Screen
4. Screen returning a TabTemplate with one tab
5. That tab embeds a NavigationTemplate with a SurfaceCallback
6. SurfaceCallback.onSurfaceAvailable() draws a solid color rectangle on the Canvas
7. Fine-grained Bazel test targets (one per test class, NOT one monolithic target)
8. Golden screenshots: capture via `adb shell screencap` and commit to goldens/. The PR MUST include visual evidence of the solid-color rectangle rendering on the DHU surface.

All source goes under android/. You own android/BUILD.bazel.
Do NOT modify proto/ files or any shared BUILD files.
If you discover a missing proto field or RPC method, message the team lead.

Use Kotlin. Depend on the proto targets in proto/vanpilot/v1/ (java_lite_proto_library and java_grpc_library targets).

When done, create a PR with `gh pr create`. Include golden screenshots in the PR.
```

### Agent: `supervisor`

**Worktree:** `worktrees/supervisor`
**Branch:** `feature/supervisor-skeleton`
**Phase:** 4 (Supervisor Skeleton)

**Prompt:**
```
You are the supervisor agent for VanPilot. Read CLAUDE.md and docs/PLAN.md first.

Your job is Phase 4: Supervisor Skeleton.

Deliverables (TDD — write failing tests first):
1. Python package under supervisor/src/
2. gRPC server implementing SyncService.GetEvents (returns hardcoded events for now)
3. Basic tmux session launcher (starts a single tmux session)
4. Fine-grained Bazel test targets (one per test module, NOT one monolithic target)

All source goes under supervisor/. You own supervisor/BUILD.bazel.
Do NOT modify proto/ files or any shared BUILD files.
If you discover a missing proto field or RPC method, message the team lead.

Use the Python proto stubs from proto/vanpilot/v1/ (py_proto_library targets).
Use rules_python for your Bazel targets.

When done, create a PR with `gh pr create`.
```

### Agent: `mcp`

**Worktree:** `worktrees/mcp`
**Branch:** `feature/mcp-skeleton`
**Phase:** 5 (MCP Server Skeleton)

**Prompt:**
```
You are the mcp agent for VanPilot. Read CLAUDE.md and docs/PLAN.md first.

Your job is Phase 5: MCP Server Skeleton.

Deliverables (TDD — write failing tests first):
1. Python package under mcp/src/
2. MCP tool definitions: display_bitmap, submit_bitmap, get_screenshot
3. Stub implementations that return mock responses
4. .mcp.json config file for agent discovery (goes in repo root)
5. Fine-grained Bazel test targets (one per test module, NOT one monolithic target)

All source goes under mcp/. You own mcp/BUILD.bazel.
The .mcp.json file goes in the repo root.
Do NOT modify proto/ files or any shared BUILD files.
If you discover a missing proto field or RPC method, message the team lead.

Use rules_python for your Bazel targets.

When done, create a PR with `gh pr create`.
```

### Agent: `reviewer`

**Worktree:** none (works from repo root)
**Branch:** main

**Prompt:**
```
You are the reviewer agent for VanPilot. Read CLAUDE.md, PARALLEL_STRATEGY.md, and sandbox/claude-sandbox/PARALLEL_STRATEGY.md first.

Your job is to review all PRs created by feature agents. When the team lead assigns you a PR, review it against:

Shared checklist (from sandbox/claude-sandbox/PARALLEL_STRATEGY.md):
1. Tests exist with adequate coverage
2. Tests pass (CI green)
3. Visual baselines included if PR changes UI (block if missing)
4. Existing baselines updated if PR changes styling/layout
5. Code quality — clean code, follows conventions
6. No auto-merge

VanPilot addenda (from PARALLEL_STRATEGY.md):
1. Golden images — any Android Auto UI PR must include golden screenshot diffs
2. Fine-grained Bazel targets — no monolithic test targets
3. Proto codegen consistency — if .proto files changed, stubs must be regenerated
4. No Gradle — reject any Gradle build files

Post your review on the GitHub PR using `gh pr review`.
Then DM the agent who created the PR: "Review posted on PR #N, please address comments."
Do NOT approve PRs that are missing golden screenshots for UI changes.
```

---

## Team Lead Coordination Notes

### Spawn Order

Spawn agents ONE AT A TIME. Before each spawn, `cd` to the correct worktree directory. This works around the cwd inheritance bug (Lesson #1).

```
cd worktrees/android   → spawn android
cd worktrees/supervisor → spawn supervisor
cd worktrees/mcp       → spawn mcp
cd /repo/root          → spawn reviewer
```

### Merge Order

When all three PRs are ready and reviewed:

1. **`mcp` first** — smallest footprint, fewest files, least conflict potential
2. **`supervisor` second** — independent Python package
3. **`android` last** — largest changeset, most integration risk

After each merge, remaining agents rebase onto updated main.

### Shutdown Policy

- Shut down `mcp` agent immediately after its PR merges (smallest scope, frees ~600 MB)
- Shut down `supervisor` after its PR merges
- Shut down `android` after its PR merges
- Keep `reviewer` alive if proceeding to Phase 6, otherwise shut down

### Memory Budget

| Component | Estimated RSS |
|---|---|
| Lead baseline (lead + Bazel + container) | ~1.4 GB |
| 3 feature agents (600 MB each) | ~1.8 GB |
| 1 reviewer agent | ~600 MB |
| Android emulator + DHU (android agent only) | ~2-3 GB |
| **Peak total** | **~6.8 GB** |
| **Available (12 GB sandbox)** | **~5.2 GB buffer** |

Only the `android` agent needs the emulator. No contention in Wave 1.

### If an Agent Hits Context Limits

The agent should write a `HANDOFF.md` in its worktree before dying. Respawn with a new name (e.g., `android-2`) and point it at the HANDOFF.md.

### Proto Change Protocol

If any agent discovers a missing proto field or RPC method:
1. Agent messages team lead
2. Team lead evaluates the change
3. Team lead makes the proto edit on main (or spawns a short-lived agent)
4. All agents rebase onto updated main

---

## After Wave 1

Once all three PRs merge, proceed to:
- **Phase 6 (Docker Setup)** — serial, team lead or single agent
- Then **Wave 3 (Phases 7/8/9)** — new team with `grpc-e2e`, `voice`, `golden` agents

See `PARALLEL_STRATEGY.md` for Wave 3 team structure.

---

## Verification

Before launching the team, verify:
```bash
# Agent teams enabled
echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS  # should print 1

# Build system works
bazel build //...

# Proto targets exist
bazel query 'kind("py_proto_library", //proto/...)'
bazel query 'kind("java_lite_proto_library", //proto/...)'

# No uncommitted changes
git status  # should be clean on main
```
