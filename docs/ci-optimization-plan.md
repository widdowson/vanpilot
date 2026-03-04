# CI Optimization Plan

**Issue**: [#111](https://github.com/widdowson/vanpilot/issues/111) — GitHub Actions billing alarm
**Date**: 2026-03-04
**Author**: ci-auditor agent

---

## 1. Current State

### Workflows

| Workflow | Runner | Trigger | Purpose |
|----------|--------|---------|---------|
| `ci.yml` | `macos-latest` | push to `main`, PRs to `main` | Build all targets, run all tests, upload APK + goldens |
| `test-plan-check.yml` | `ubuntu-latest` | PR open/edit/sync | Verify PR test-plan checklist items are checked |

The test-plan-check workflow is negligible (1-minute timeout, ubuntu runner, no build).
**All billing pressure comes from `ci.yml`.**

### Step-by-step timing (sampled from 5 representative runs)

| Step | Best (cached) | Typical | Worst (cold) |
|------|---------------|---------|--------------|
| Set up Bazel (restore caches) | 0.9m | 3.2m | 3.9m |
| Set up Android SDK | 0.1m | 0.1m | 0.2m |
| **Build all targets** | **8.8m** | **13.6m** | **17.1m** |
| **Run all tests** | **1.2m** | **1.4m** | **1.5m** |
| Post Set up Bazel (save caches) | 0.1m | 0.5m | 7.4m |
| **Total job** | **11m** | **14m** | **29m** |

Key observation: **Build dominates at 65-85% of total time.** Tests are fast (1-2 minutes) because Bazel builds test binaries during the build step, and tests themselves are lightweight (Robolectric, Python unittest).

### Trigger pattern (last 100 CI runs)

- `pull_request`: 73 runs (73%)
- `push` (to main after merge): 27 runs (27%)

Every merged PR triggers **two** CI runs: one for the PR itself, one for the push-to-main merge. During the sprint of 2026-03-04, this doubled throughput produced 93 CI runs in 24 hours.

### Billing impact

| Metric | Value |
|--------|-------|
| CI runs (last 200) | 200 |
| Total wall minutes | 1,456 |
| **Total billed minutes (10x macOS)** | **15,550** |
| GitHub Free tier limit | 2,000 min/month |
| GitHub Pro tier limit | 3,000 min/month |
| **Overage (Free tier, 3-day sprint)** | **~13,550 min over** |
| **Estimated overage cost** ($0.08/min macOS) | **~$1,084** |

The cache usage is 10.7 GB across 75 active caches (GitHub allows 10 GB per repo).

### What Bazel builds

The `bazel build //...` and `bazel test //...` commands build and test everything:

- **Android**: APK binary, ~30 `android_local_test` targets (Kotlin + Robolectric)
- **Python**: Supervisor (~18 `py_test`), MCP (~7 `py_test`), Instance Manager (~10 `py_test`), e2e (~2 `py_test`)
- **Proto**: 4 proto files generating Java + Python stubs + gRPC services
- **Tools**: 1 `kt_jvm_test` build canary

The build graph is heavy because:
1. Kotlin compilation (kotlinc) is slow
2. Proto + gRPC Java code generation pulls in a large dependency tree
3. Maven dependency resolution (15 artifacts from Google + Maven Central)
4. Robolectric downloads a ~100 MB Android SDK JAR on first use

---

## 2. Top Time Sinks (Ranked)

### #1: macOS runner with 10x billing multiplier (~80% of cost)

The CI runs on `macos-latest` because:
- Android SDK setup
- Robolectric tests that need macOS (allegedly)

However, **none of these actually require macOS**:
- The Android SDK is available on Linux via `android-actions/setup-android`
- Robolectric runs on Linux (it's JVM-only, no emulator)
- Python tests have zero OS dependency
- The APK is cross-compiled, not host-dependent

**Switching to `ubuntu-latest` immediately cuts billed minutes by 10x** — from 15,550 to 1,555 for the same workload.

### #2: Duplicate runs on PR merge (push + pull_request triggers)

Every merged PR triggers CI twice: once for the PR (`pull_request`), once for the merge commit pushed to `main` (`push`). The concurrency group cancels in-progress PR runs when a new commit appears on the same PR, but does not prevent the post-merge `push` run.

~27% of CI runs (27/100) are post-merge push runs that re-validate already-tested code. Removing or skipping these saves ~27% of minutes.

### #3: Build without test caching (`build //...` then `test //...`)

The workflow runs `bazel build //...` followed by `bazel test //...` as two separate steps. Bazel's test command already builds test dependencies, so the explicit `build //...` is redundant **for test execution**. However, `build //...` is needed to produce the APK artifact.

A more efficient approach: `bazel test //... --build_tests_only` combined with a separate targeted `bazel build //android:vanpilot` for the APK.

### #4: Cold Bazel cache on dependency changes

When `MODULE.bazel` or `requirements.txt` changes, the Bazel external cache is invalidated and everything is re-fetched and re-built from scratch. The truth version bump PR took 29 minutes (vs typical 14 minutes) because the Maven dependency tree was re-resolved.

### #5: No path filtering — all code built on every change

A Python-only change (e.g., `supervisor/src/watchdog.py`) triggers a full Android build + Kotlin compilation + proto generation. Python tests take ~30 seconds to run; the Android build that precedes them takes 10+ minutes.

---

## 3. Recommendations (Ordered by Impact)

### R1: Switch to `ubuntu-latest` runner
**Estimated savings: 90% of billed minutes (10x multiplier eliminated)**
**Effort: Low (1-line change + validation)**

Change `runs-on: macos-latest` to `runs-on: ubuntu-latest` in `ci.yml`. The Android SDK, Kotlin compiler, Robolectric, and Python all work identically on Linux.

Verify by:
1. Running `bazel test //...` locally on a Linux machine or Docker container
2. Creating a test PR with the runner change

If any macOS-specific issue surfaces (unlikely), fall back to macOS only for the affected subset.

### R2: Remove `push` trigger from `ci.yml` (or make it conditional)
**Estimated savings: ~27% of remaining minutes**
**Effort: Low (1-line change)**

Option A — Remove entirely:
```yaml
on:
  pull_request:
    branches: [main]
  # push trigger removed — PR CI is sufficient
```

Option B — Only run on push when no PR was associated:
```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
    # Only build APK on push, skip tests
```

The PR run already validates the exact merge commit (GitHub uses `refs/pull/N/merge`). Re-running on the push to `main` is redundant unless a non-PR push occurs (e.g., direct commit to main, which should be disallowed by branch protection anyway).

### R3: Split into path-filtered jobs
**Estimated savings: 50-80% of build time for Python-only and proto-only changes**
**Effort: Medium (workflow refactor)**

Replace the single `test` job with path-filtered jobs:

```yaml
jobs:
  android:
    if: contains(needs.changes.outputs.paths, 'android') || contains(needs.changes.outputs.paths, 'proto')
    runs-on: ubuntu-latest
    steps:
      - run: bazel test //android/... //tools/build-verify/...

  python:
    if: contains(needs.changes.outputs.paths, 'python') || contains(needs.changes.outputs.paths, 'proto')
    runs-on: ubuntu-latest
    steps:
      - run: bazel test //supervisor/... //mcp/... //instance_manager/... //e2e/...

  proto:
    if: contains(needs.changes.outputs.paths, 'proto')
    runs-on: ubuntu-latest
    steps:
      - run: bazel build //proto/...
```

Use `dorny/paths-filter` or GitHub's native path filters to detect changed directories. The `push` to `main` trigger (if retained) should always run all jobs.

### R4: Use `bazel test //... --build_tests_only` and targeted APK build
**Estimated savings: ~1-2 minutes per run**
**Effort: Low (2-line change)**

Replace:
```yaml
- run: bazel build //...
- run: bazel test //...
```

With:
```yaml
- run: bazel build //android:vanpilot  # APK only
- run: bazel test //... --build_tests_only  # Tests (builds deps automatically)
```

Or even combine into one step:
```yaml
- run: bazel test //... --build_tests_only && bazel build //android:vanpilot
```

### R5: Cancel redundant push-to-main runs
**Estimated savings: avoids wasted minutes on cancelled runs**
**Effort: Low**

The existing concurrency group handles PRs but the push-to-main group key is `CI-refs/heads/main`, which means successive main merges cancel each other. This is actually good behavior. Keep it.

### R6: Workflow concurrency — limit total parallel CI runs
**Estimated savings: prevents burst billing during agent sprints**
**Effort: Low**

During the recent sprint, 93 CI runs occurred in 24 hours. Adding a queue limit prevents runaway costs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

This already exists. Enhance it to also cancel stale push-to-main runs more aggressively.

---

## 4. Bazel Caching Strategy

### Current cache setup

The workflow uses `bazel-contrib/setup-bazel@0.14.0` with:
- `bazelisk-cache: true` — caches the Bazel binary itself
- `disk-cache: ${{ github.workflow }}` — persists Bazel's disk cache in GitHub Actions cache
- `repository-cache: true` — caches downloaded external repos
- `external-cache: true` — caches external workspace symlinks

The `.bazelrc` sets `build:ci --disk_cache=` (empty) to let setup-bazel manage it.

There's also a `BAZEL_REMOTE_CACHE_URL` secret slot for a proper remote cache, but it's not configured.

### Recommended: GitHub Actions cache as Bazel disk cache (current approach, keep it)

The current `setup-bazel` approach is already solid for this project's scale. The 75 active caches / 10.7 GB usage shows it's working. The main issue isn't cache misses — it's the **runner cost multiplier** and **run volume**.

### Optional future: Remote cache for local + CI sharing

If the project grows significantly, consider:

1. **BuildBuddy Cloud** (free tier: 10 GB cache, unlimited builds)
   - Add to `.bazelrc`: `build:ci --remote_cache=grpcs://remote.buildbuddy.io`
   - Set `BUILDBUDDY_API_KEY` as a repo secret
   - Also works for local dev builds, sharing cache between CI and developers

2. **Self-hosted `bazel-remote`** on the Mac Studio
   - Run via Docker: `docker run -p 9092:9092 buchgr/bazel-remote`
   - CI connects via Tailscale: `--remote_cache=grpc://mac-studio:9092`
   - Zero egress cost, fastest possible cache hits

3. **Google Cloud Storage bucket**
   - Only if already using GCP
   - Set `BAZEL_REMOTE_CACHE_URL` secret to `https://storage.googleapis.com/vanpilot-bazel-cache`

**Recommendation for now**: The current setup-bazel caching is adequate. Focus on runner cost (R1) and run volume (R2, R3) first. Add a remote cache only if build times remain problematic after those changes.

---

## 5. Bazel Sidecar / Persistent Server

### In CI: Not practical

GitHub Actions runners are ephemeral — each run gets a fresh VM. There's no way to keep a Bazel server process running between CI runs. The setup-bazel cache restoration effectively simulates this by preserving the disk cache.

### For local development: Already works

Bazel runs a persistent server locally (`bazel info server_pid`). After the first build, subsequent builds are incremental. No additional sidecar is needed.

### Performance tuning for CI

Add to `.bazelrc`:
```
build:ci --jobs=auto
build:ci --local_ram_resources=HOST_RAM*.8
build:ci --local_cpu_resources=HOST_CPUS
```

GitHub-hosted runners have 4 vCPUs / 14 GB RAM (ubuntu) or 3 vCPUs / 14 GB RAM (macOS). Bazel defaults are usually fine, but explicit settings prevent under-utilization.

---

## 6. Implementation Plan

### Phase 1: Quick wins (estimated savings: 90%+ of billed minutes)

| Step | Change | Effort | PR |
|------|--------|--------|----|
| 1.1 | Change `runs-on: macos-latest` → `ubuntu-latest` | 5 min | Single PR |
| 1.2 | Remove `push` trigger from `ci.yml` (keep PR-only) | 2 min | Same PR |
| 1.3 | Replace `bazel build //...` + `bazel test //...` with targeted build | 5 min | Same PR |
| 1.4 | Validate on a test PR | 15 min | Test |

Expected result: **~14 minutes wall time → ~14 minutes billed** (vs 140 minutes billed today per run).

### Phase 2: Path filtering (estimated additional savings: 50-80% on non-Android PRs)

| Step | Change | Effort |
|------|--------|--------|
| 2.1 | Add `dorny/paths-filter` step | 10 min |
| 2.2 | Split into `android`, `python`, `proto` jobs | 30 min |
| 2.3 | Test with Python-only and Android-only changes | 15 min |

### Phase 3: Remote cache (optional, for future scale)

| Step | Change | Effort |
|------|--------|--------|
| 3.1 | Sign up for BuildBuddy free tier | 10 min |
| 3.2 | Add `BUILDBUDDY_API_KEY` secret | 5 min |
| 3.3 | Add `--remote_cache` to `.bazelrc` | 5 min |
| 3.4 | Verify cache hits on consecutive CI runs | 15 min |

### Phase 4: CI tuning (polish)

| Step | Change | Effort |
|------|--------|--------|
| 4.1 | Add `--local_ram_resources` / `--jobs` tuning to `.bazelrc` | 5 min |
| 4.2 | Add `--test_sharding_strategy=disabled` (tests are already fast) | 2 min |
| 4.3 | Enable branch protection to prevent direct pushes to main | 5 min |

---

## Summary

| Optimization | Billed min savings | Cumulative effect |
|---|---|---|
| **R1: ubuntu runner** | 90% (10x → 1x multiplier) | 15,550 → 1,555 |
| **R2: Remove push trigger** | 27% of remaining | 1,555 → 1,135 |
| **R3: Path filtering** | 50-80% on subset | 1,135 → ~600 |
| **R4: Targeted build** | ~10% | ~540 |
| **Combined** | **~96% reduction** | **15,550 → ~540** |

With Phase 1 alone (ubuntu + no push trigger), the 3-day sprint that triggered the billing alarm would have cost **~1,135 billed minutes instead of ~15,550** — well within the free tier for a full month.
