# Golden Screenshots

This directory contains golden (reference) screenshots for VanPilot's UI states. These images are the primary visual verification mechanism for code review.

## How It Works

1. Each UI state has a corresponding golden image (PNG).
2. Bazel test targets render the UI in the Android emulator + Android Auto DHU, capture a screenshot, and compare it pixel-by-pixel against the golden.
3. If pixels differ beyond a configurable tolerance, the test fails and produces a diff image.
4. When a PR changes UI behavior, updated golden images appear in the PR diff. Reviewers compare before/after to verify correctness.

## Naming Convention
```
goldens/
├── auto_dashboard_day.png         # Main dashboard, daytime palette
├── auto_dashboard_night.png       # Main dashboard, nighttime palette
├── auto_tab_lead_agent.png        # Lead agent conversation tab
├── auto_tab_sub_agent.png         # Sub-agent conversation tab
├── auto_offline_indicator.png     # Offline/disconnected state
├── auto_visual_card_history.png   # Visual card history browsing
├── phone_minimal_transcript.png   # Phone fallback: text transcript
└── ...
```

## Adding New Goldens

When adding a new UI state or feature:

1. Write the golden test that renders the state and captures a screenshot.
2. Run the test once to generate the initial golden image.
3. Visually verify the generated image is correct.
4. Commit the image to this directory.
5. The test now passes by comparing future renders against this golden.

## Updating Goldens

When changing existing UI behavior:

1. Run the affected golden tests. They will fail and produce diff images.
2. Review the diff images to confirm the changes are intentional.
3. Regenerate the golden images (e.g., `bazel run //android:update_goldens`).
4. Commit the updated images. The PR diff shows before/after.

## Video Capture

For debugging, enable video capture with `--test_arg=--record-video`. This captures the last 5 seconds (configurable) leading up to the golden frame. Videos are written to a temp directory and are NOT committed.