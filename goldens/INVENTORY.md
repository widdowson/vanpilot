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

## 1. Visual Card Tab (NavigationTemplate + SurfaceCallback)

The Visual tab uses a `NavigationTemplate` with a raw `Surface` rendered by
`VanPilotSurfaceCallback`. Two rendering modes exist: solid-color default and
bitmap display.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 1.1 | Default teal — light mode | `phase3/solid_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#1A8A7D`. Not a real DHU capture. |
| 1.2 | Default teal — dark mode | `phase3/solid_dark_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#0D4540`. Not a real DHU capture. |
| 1.3 | Default teal — DHU light mode | — | MISSING | Full DHU screenshot with tab bar, status bar, AA chrome. |
| 1.4 | Default teal — DHU dark mode | — | MISSING | Same as 1.3 but in dark mode. |
| 1.5 | Custom bitmap displayed | — | MISSING | After `displayBitmap()` is called with a cached bitmap. |
| 1.6 | Bitmap cleared (return to teal) | — | MISSING | After `clearBitmap()` — should return to solid teal. |

**Source**: `VanPilotSurfaceCallback.kt` lines 83-93, 99-105, 107-140.
**Theme**: `DarkModeTheme.kt` — light `#1A8A7D`, dark `#0D4540`.

---

## 2. Lead Agent Tab (ListTemplate)

The Lead Agent tab shows a `ListTemplate` with conversation messages rendered as
`Row` items. Each row has a title (message text) and secondary text (sender).

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 2.1 | Empty conversation | — | MISSING | Shows "No messages yet" placeholder row. |
| 2.2 | Populated conversation (mock data) | — | MISSING | 3 mock messages from `createWithMockData()`. |
| 2.3 | Max messages (100) | — | MISSING | Verify scroll/truncation at `MAX_MESSAGES_PER_TAB = 100`. |

**Source**: `VanPilotScreen.kt` lines 118-121, 141-169.
**Mock data**: `ConversationTabManager.kt` lines 33-42 — 3 lead agent messages.

---

## 3. Sub-Agent Tabs (ListTemplate)

Each sub-agent gets its own tab. Maximum 2 sub-agent tabs (4 tabs total limit).

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 3.1 | Single sub-agent — "Researcher" | — | MISSING | 2 mock messages for "researcher" agent. |
| 3.2 | Second sub-agent — "Coder" | — | MISSING | 1 mock message for "coder" agent. |
| 3.3 | Sub-agent with empty conversation | — | MISSING | "No messages yet" placeholder. |

**Source**: `VanPilotScreen.kt` lines 93-105, 122-127.
**Mock data**: `ConversationTabManager.kt` lines 45-62 — researcher (2 msgs), coder (1 msg).

---

## 4. Tab Bar States

The `TabTemplate` shows up to 4 tabs. Tab switching changes the active tab highlight
and swaps the content area.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 4.1 | Visual tab selected (default) | — | MISSING | Visual tab active, others inactive. |
| 4.2 | Lead Agent tab selected | — | MISSING | Lead Agent tab active, content = message list. |
| 4.3 | Sub-agent tab selected | — | MISSING | Sub-agent tab active. |
| 4.4 | All 4 tabs visible | — | MISSING | Visual + Lead + 2 sub-agents at max capacity. |
| 4.5 | 2 tabs only (no sub-agents) | — | MISSING | Only Visual + Lead Agent when no sub-agents registered. |
| 4.6 | Stale tab fallback | — | MISSING | `activeTabId` not in `validTabIds` — falls back to Visual. |

**Source**: `VanPilotScreen.kt` lines 63-135 — `onGetTemplate()`.

---

## 5. Connection State Indicators

The `ConnectionState` enum defines visual indicators for connectivity. Per AC-9.2,
a disconnect indicator is visible in the action strip. The connection indicator is
the first action in the NavigationTemplate action strip, rendered as a tinted icon:
- CONNECTED: green tint
- DISCONNECTED: red tint (default state)
- RECONNECTING: yellow tint

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 5.1 | Connected (green indicator) | `captured/connection_connected.png` | MISSING | After `ConnectionMonitor.onRpcSuccess()`. Green-tinted icon in action strip. |
| 5.2 | Disconnected (red indicator) | `captured/connection_disconnected.png` | MISSING | Default state. Red-tinted icon in action strip. |
| 5.3 | Reconnecting (yellow indicator) | `captured/connection_reconnecting.png` | MISSING | After `onReconnectAttempt()`. Yellow-tinted icon in action strip. |

**Source**: `ConnectionState.kt`, `ConnectionMonitor.kt`, `VanPilotScreen.kt` lines 128-139.
**Tests**: `//goldens:connection_disconnected_golden_test`, `//goldens:connection_connected_golden_test`, `//goldens:connection_reconnecting_golden_test`.

---

## 6. Surface Lifecycle States

The `SurfaceCallback` tracks visible area and stable area insets from the host.
Different head units report different dimensions.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 6.1 | Standard DHU surface (800x480) | `phase9/emulator_screenshot.png` | HAS | Single emulator capture exists. |
| 6.2 | Wide surface (1024x480) | — | MISSING | Wide-aspect head unit. |
| 6.3 | Visible area insets applied | — | MISSING | When `onVisibleAreaChanged` constrains rendering. |

**Source**: `VanPilotSurfaceCallback.kt` lines 59-76.

---

## 7. History Navigation States

The `DisplayHistory` class tracks ordered history of displayed cache keys.
Back/forward buttons in the action strip enable/disable based on history position.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 7.1 | Initial (both disabled) | `captured/history_initial.png` | MISSING | No history entries — both back and forward disabled. |
| 7.2 | Back enabled | `captured/history_back_enabled.png` | MISSING | After 2+ display entries, back arrow is enabled. |
| 7.3 | Forward enabled | `captured/history_forward_enabled.png` | MISSING | After going back, forward arrow is enabled. |

**Source**: `DisplayHistory.kt`, `VanPilotScreen.kt` lines 211-231.
**Tests**: `//goldens:history_initial_golden_test`, `//goldens:history_back_enabled_golden_test`, `//goldens:history_forward_enabled_golden_test`.

---

## 8. Combined Action Strip

The full action strip on the Visual tab shows all 4 actions together.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 8.1 | Full action strip (all 4 buttons) | `captured/full_action_strip.png` | MISSING | Connection indicator + PAN + back + forward in default state. |

**Source**: `VanPilotScreen.kt` lines 128-147.
**Test**: `//goldens:full_action_strip_golden_test`.

---

## 9. Dark Mode Transitions

Android Auto can toggle dark mode via configuration change. `onGetTemplate()` reads
`carContext.isDarkMode` on every refresh.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 9.1 | Light to Dark transition | — | MISSING | Before/after pair showing theme change. |
| 9.2 | Dark to Light transition | — | MISSING | Before/after pair showing theme change. |

**Source**: `VanPilotScreen.kt` lines 36-39, 67.

---

## Summary

| Category | Total States | Existing | Missing |
|----------|-------------|----------|---------|
| Visual Card Tab | 6 | 2 (synthetic) | 4 |
| Lead Agent Tab | 3 | 0 | 3 |
| Sub-Agent Tabs | 3 | 0 | 3 |
| Tab Bar States | 6 | 0 | 6 |
| Connection States | 3 | 0 | 3 |
| Surface Lifecycle | 3 | 1 | 2 |
| History Navigation | 3 | 0 | 3 |
| Combined Action Strip | 1 | 0 | 1 |
| Dark Mode Transitions | 2 | 0 | 2 |
| **Total** | **30** | **3** | **27** |

### Priority for capture

1. **P0 — Core states** (must have before any PR review is meaningful):
   - 1.3, 1.4 (DHU teal, light/dark)
   - 2.2 (lead agent with messages)
   - 3.1 (sub-agent with messages)
   - 4.4 (all 4 tabs visible)

2. **P1 — Edge cases** (important for regression):
   - 1.5 (bitmap displayed)
   - 2.1 (empty conversation)
   - 4.5 (2 tabs only)
   - 5.1-5.3 (connection indicator states — now wired into action strip)
   - 7.1-7.3 (history navigation states)
   - 8.1 (full action strip)

3. **P2 — Advanced** (nice to have):
   - Surface size variations
   - Dark mode transitions
