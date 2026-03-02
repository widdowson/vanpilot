# VanPilot Acceptance Criteria

This document defines the acceptance criteria for VanPilot development. All features must meet these criteria before merging to main.

## AC-1: Build System

- [x] **AC-1.1**: The project uses Bazel as its sole build system. No Gradle wrappers, no npm, no secondary build orchestrators.
- [x] **AC-1.2**: Bazel's native Android rules are used for building, testing, and packaging the Android app. Hermeticity and parallelism are non-negotiable.
- [x] **AC-1.3**: Individual test targets are fine-grained. There must be no single monolithic test target that delegates to another testing framework. Each logical test case or test suite should be its own Bazel test target.
- [x] **AC-1.4**: `bazel test //...` runs all tests. `bazel build //...` builds all artifacts.
- [x] **AC-1.5**: Bazel remote caching is configured where beneficial.

## AC-2: Test-Driven Development

- [x] **AC-2.1**: All features are developed test-first. A commit that adds a feature must contain: (1) a commit with failing tests, followed by (2) a commit with the implementation that makes them pass. Squashing is acceptable, but the PR description must indicate the TDD flow.
- [x] **AC-2.2**: Test coverage is high. Every public API surface, every gRPC endpoint, every proto message serialization path, and every UI state transition must have test coverage.
- [x] **AC-2.3**: Tests are hermetic. No test depends on network access, external services, or mutable shared state.

## AC-3: Golden Pixel Diff Testing

- [x] **AC-3.1**: All UI states rendered on the Android Auto head unit have corresponding golden screenshot images committed to the `goldens/` directory.
- [x] **AC-3.2**: When a feature changes the visual output, the golden images are updated in the same PR. The diff of golden images (before/after) is the primary visual review mechanism.
- [x] **AC-3.3**: When a new UI mode or visual feature is added, new golden images are added in the same PR. The PR reviewer (human) can compare the golden against the stated requirements.
- [x] **AC-3.4**: Golden tests run as Bazel test targets. They launch the Android emulator + Android Auto DHU, render the UI in the specified state, capture a screenshot, and compare against the committed golden. Pixel differences beyond a configurable tolerance fail the test.
- [x] **AC-3.5**: Golden tests produce clear diff images (highlighting changed pixels) when they fail, stored as test outputs.

## AC-4: Video Capture (Optional Diagnostic)

- [x] **AC-4.1**: A Bazel test flag (e.g., `--test_arg=--record-video`) enables video capture of emulator UI flows during test execution.
- [ ] **AC-4.2**: Video captures the last N seconds (configurable, default 5) leading up to the golden frame capture.
- [x] **AC-4.3**: Videos are written to a temporary directory and are NOT committed to the repository.
- [x] **AC-4.4**: Video capture is disabled by default and incurs no overhead when off.

## AC-5: gRPC Protocol

- [x] **AC-5.1**: All communication between the Android app and the Mac Studio supervisor is defined in `.proto` files under `proto/vanpilot/v1/`.
- [x] **AC-5.2**: The `GetEvents` RPC implements timestamp-based pagination as described in DESIGN.md. It is idempotent — the same request always returns at least the same data.
- [x] **AC-5.3**: Event payloads use `oneof` to distinguish between `TextMessage`, `DisplayCommand`, `BitmapPayload`, `WatchdogTimeout`, and `InputDeliveryFailure`.
- [x] **AC-5.4**: Bidirectional gRPC is implemented: the Android app can call the supervisor, and the supervisor can call the Android app.
- [x] **AC-5.5**: Adaptive batching is implemented: `max_count` adjusts based on connection health.

## AC-6: Display MCP

- [x] **AC-6.1**: The display MCP exposes `display_bitmap(cache_key, blocking)`, `submit_bitmap(image_data)`, and `get_screenshot()` tools.
- [x] **AC-6.2**: `display_bitmap` with `blocking=false` returns immediately.
- [ ] **AC-6.3**: `display_bitmap` with `blocking=true` holds until the Android app confirms display.
- [x] **AC-6.4**: `submit_bitmap` returns the assigned cache key and a courtesy screenshot showing the rendered result at correct head unit dimensions.
- [ ] **AC-6.5**: The MCP runs inside the Docker container alongside the Claude Code agents.

## AC-7: Bitmap Caching

- [x] **AC-7.1**: The Android app maintains an in-memory bitmap cache keyed by hex tokens.
- [x] **AC-7.2**: When `display_bitmap` references a missing key, the app automatically requests it via `GetBitmap`.
- [x] **AC-7.3**: The supervisor tracks which keys have been sent to the Android app.
- [x] **AC-7.4**: On reconnection, the supervisor and app reconcile cache state.
- [x] **AC-7.5**: The lead agent can flip between cached images without retransmission.

## AC-8: Voice I/O

- [x] **AC-8.1**: Speech-to-text runs entirely on-device (no cloud API calls). Phase 1 complete: Android's built-in `SpeechRecognizer` with offline language pack is implemented. Phase 2 (local Whisper.cpp model for improved accuracy) is pending.
- [x] **AC-8.2**: Text-to-speech runs entirely on-device (no cloud API calls).
- [x] **AC-8.3**: Voice input is disabled during read-only (offline) mode.
- [x] **AC-8.4**: Incoming text messages are spoken aloud via TTS as they arrive.

## AC-9: Offline Resilience

- [x] **AC-9.1**: The app detects loss of connectivity to the Mac Studio.
- [x] **AC-9.2**: In offline mode: voice input is disabled, last bitmap is retained, disconnect indicator is visible in the tab bar.
- [x] **AC-9.3**: Tab navigation and history browsing remain functional offline.
- [x] **AC-9.4**: On reconnection, sync resumes from the last known timestamp using `GetEvents`.
- [x] **AC-9.5**: Adaptive batching starts conservatively on reconnection and increases.

## AC-10: Android Auto Integration

- [x] **AC-10.1**: The VanPilot app is a navigation-category `androidx.car.app` app using the Car App Library. It declares `androidx.car.app.NAVIGATION_TEMPLATES` and `androidx.car.app.ACCESS_SURFACE` permissions.
- [ ] **AC-10.2**: The app renders correctly on a 13-inch head unit display alongside Maps and Spotify.
- [x] **AC-10.3**: The top-level template is a `TabTemplate`. Tab navigation works via touch on the head unit.
- [x] **AC-10.4**: The Visual Card tab uses a `NavigationTemplate` with a `SurfaceCallback` to blit cached PNG bitmaps onto the `Surface`. Visual card history is browsable via action strip buttons.
- [x] **AC-10.5**: Conversation tabs (lead agent, sub-agents) use `ListTemplate` to display text message feeds.
- [x] **AC-10.6**: The app supports dark mode via `carContext.isDarkMode()` and forwards the theme to the supervisor for agent rendering context.
- [x] **AC-10.7**: The app can be fully tested using Android Studio's emulator + Android Auto DHU without physical hardware.

## AC-11: Security

- [ ] **AC-11.1**: The head unit never receives credentials, API keys, or gRPC traffic.
- [ ] **AC-11.2**: All gRPC traffic is tunneled through Tailscale.
- [ ] **AC-11.3**: Claude Code agents run in Docker with resource limits.

## AC-12: CI/CD

- [x] **AC-12.1**: GitHub Actions runs `bazel test //...` on every pull request.
- [x] **AC-12.2**: The `main` branch has branch protection enabled: status checks must pass, code review is required, force pushes are blocked, and stale reviews are dismissed on new commits.
- [x] **AC-12.3**: Golden image diffs are visible in PR artifacts.
- [x] **AC-12.4**: CI must pass before any PR can merge to main.

## AC-13: Input Injection

- [x] **AC-13.1**: The supervisory process can inject user prompts into the lead agent's tmux session via `tmux send-keys`.
- [x] **AC-13.2**: After injection, the supervisor monitors for a response within a configurable timeout.
- [x] **AC-13.3**: If no response is detected, an `InputDeliveryFailure` event is emitted.
- [ ] **AC-13.4**: (Stretch Goal) Investigate protocol spoofing as an alternative input injection path. Document findings regardless of outcome.

## AC-14: Watchdog

- [x] **AC-14.1**: The supervisory process monitors each agent's tmux session for output activity.
- [x] **AC-14.2**: If no output is detected within a configurable timeout, a `WatchdogTimeout` event is emitted.
- [x] **AC-14.3**: The Android app displays watchdog alerts to the user.