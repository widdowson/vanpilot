# Golden Screenshot Inventory

Comprehensive list of every UI state in the VanPilot Android Auto app that requires
a golden screenshot. Derived from source code analysis of the Kotlin UI layer.

## Legend

| Status | Meaning |
|--------|---------|
| **HAS** | Golden exists and is committed |
| **GENERATED** | Synthetic golden (not from emulator/DHU) |
| **MISSING** | No golden exists — needs capture |

---

## Architecture Note

As of commit 3078421, `VanPilotScreen` uses `NavigationTemplate` directly as the
root template (not inside `TabTemplate`). The surface layer drawn by
`VanPilotSurfaceCallback` is only visible in DHU screenshots when
`NavigationTemplate` is the root. Tab-based conversation views (Lead Agent,
Sub-Agent) will be re-added as pushed screens in a future PR.

Sections 2–4 (Lead Agent, Sub-Agent, Tab Bar) are therefore **BLOCKED** on the
pushed-screen implementation.

---

## 1. Visual Card (NavigationTemplate + SurfaceCallback)

The main screen uses a `NavigationTemplate` with a raw `Surface` rendered by
`VanPilotSurfaceCallback`. Two rendering modes exist: solid-color default and
bitmap display.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 1.1 | Default teal — light mode (synthetic) | `phase3/solid_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#1A8A7D`. Not a real DHU capture. |
| 1.2 | Default teal — dark mode (synthetic) | `phase3/solid_dark_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#0D4540`. Not a real DHU capture. |
| 1.3 | Default teal — DHU day mode | `captured/visual_card_day.png` | **HAS** | 1840x1080 DHU screenshot. Surface RGB(35,151,123). Cropped: left 80px AA chrome removed. |
| 1.4 | Default teal — DHU night mode | `captured/visual_card_night.png` | **HAS** | 1840x1080 DHU screenshot. Surface RGB(16,75,62). 64% pixel difference from day. |
| 1.5 | Custom bitmap displayed | — | MISSING | After `displayBitmap()` is called with a cached bitmap. |
| 1.6 | Bitmap cleared (return to teal) | — | MISSING | After `clearBitmap()` — should return to solid teal. |

**Source**: `VanPilotSurfaceCallback.kt` lines 83-93, 99-105, 107-140.
**Theme**: `DarkModeTheme.kt` — light `#1A8A7D`, dark `#0D4540`.

---

## 2. Lead Agent Conversation (ListTemplate) — BLOCKED

The Lead Agent conversation shows a `ListTemplate` with messages rendered as
`Row` items. **Blocked**: tabs removed from `VanPilotScreen`; conversation views
will be re-added as pushed screens.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 2.1 | Empty conversation | — | MISSING | Blocked on pushed-screen implementation. |
| 2.2 | Populated conversation (mock data) | — | MISSING | Blocked on pushed-screen implementation. |
| 2.3 | Max messages (100) | — | MISSING | Blocked on pushed-screen implementation. |

**Source**: `ConversationTabManager.kt`.

---

## 3. Sub-Agent Conversations (ListTemplate) — BLOCKED

Each sub-agent gets its own conversation view. **Blocked**: same as section 2.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 3.1 | Single sub-agent — "Researcher" | — | MISSING | Blocked on pushed-screen implementation. |
| 3.2 | Second sub-agent — "Coder" | — | MISSING | Blocked on pushed-screen implementation. |
| 3.3 | Sub-agent with empty conversation | — | MISSING | Blocked on pushed-screen implementation. |

---

## 4. Tab Bar / Navigation States — BLOCKED

Tab bar was removed when `NavigationTemplate` became root. Navigation between
views will use pushed screens in a future PR.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 4.1 | Visual card active (default) | — | MISSING | Blocked on pushed-screen implementation. |
| 4.2 | Lead Agent view active | — | MISSING | Blocked on pushed-screen implementation. |
| 4.3 | Sub-agent view active | — | MISSING | Blocked on pushed-screen implementation. |
| 4.4 | All views accessible | — | MISSING | Blocked on pushed-screen implementation. |

---

## 5. Connection State Indicators

The `ConnectionState` enum defines visual indicators for connectivity.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 5.1 | Connected (no indicator) | — | MISSING | Blocked on UI wiring. |
| 5.2 | Disconnected indicator | — | MISSING | Blocked on UI wiring. |
| 5.3 | Reconnecting indicator | — | MISSING | Blocked on UI wiring. |

**Source**: `ConnectionState.kt`.

---

## 6. Surface Lifecycle States

The `SurfaceCallback` tracks visible area and stable area insets from the host.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 6.1 | Standard DHU surface | `phase9/emulator_screenshot.png` | HAS | Legacy single emulator capture. |
| 6.2 | Wide surface (1024x480) | — | MISSING | Wide-aspect head unit. |
| 6.3 | Visible area insets applied | — | MISSING | When `onVisibleAreaChanged` constrains rendering. |

---

## 7. Dark Mode Transitions

Android Auto can toggle dark mode via configuration change. `onGetTemplate()` reads
`carContext.isDarkMode` on every refresh.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 7.1 | Light to Dark transition | — | MISSING | Covered by 1.3 + 1.4 pair. Low priority. |
| 7.2 | Dark to Light transition | — | MISSING | Covered by 1.3 + 1.4 pair. Low priority. |

---

## Summary

| Category | Total States | HAS | GENERATED | MISSING |
|----------|-------------|-----|-----------|---------|
| Visual Card | 6 | **2** | 2 | 2 |
| Lead Agent | 3 | 0 | 0 | 3 (blocked) |
| Sub-Agent | 3 | 0 | 0 | 3 (blocked) |
| Tab Bar / Nav | 4 | 0 | 0 | 4 (blocked) |
| Connection States | 3 | 0 | 0 | 3 (blocked) |
| Surface Lifecycle | 3 | 1 | 0 | 2 |
| Dark Mode Transitions | 2 | 0 | 0 | 2 (low pri) |
| **Total** | **24** | **3** | **2** | **19** |

### What we have

- **2 real DHU goldens**: `visual_card_day.png` and `visual_card_night.png` — 64% pixel difference, distinct day/night themes confirmed
- **2 synthetic goldens**: Phase 3 solid color PNGs (not from emulator)
- **1 legacy emulator screenshot**: Phase 9 capture

### What's blocked and why

Most missing goldens (13 of 19) are **blocked on pushed-screen implementation**.
The root cause: `NavigationTemplate`'s `SurfaceCallback` surface layer is not
visible in DHU screenshots when embedded inside `TabTemplate`. The fix was to make
`NavigationTemplate` the root template, which removed tab-based navigation.
Conversation views will be re-added as pushed screens in a future PR.
