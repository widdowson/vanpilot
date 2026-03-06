# Golden Screenshot Inventory

Comprehensive list of every UI state in the VanPilot Android Auto app that requires
a golden screenshot. Derived from source code analysis of the Kotlin UI layer.

## Legend

| Status | Meaning |
|--------|---------|
| **HAS** | Golden exists and is committed |
| **GENERATED** | Synthetic golden (not from emulator/DHU) |
| **MISSING** | No golden exists — needs capture |
| **BLOCKED** | Cannot capture with current tooling (see notes) |

---

## 1. Visual Card Tab (NavigationTemplate + SurfaceCallback)

The Visual tab uses a `NavigationTemplate` with a raw `Surface` rendered by
`VanPilotSurfaceCallback`. Two rendering modes exist: solid-color default and
bitmap display.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 1.1 | Default teal — light mode | `phase3/solid_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#1A8A7D`. Not a real DHU capture. |
| 1.2 | Default teal — dark mode | `phase3/solid_dark_teal_800x480.png` | GENERATED | Synthetic 800x480 PNG, color `#0D4540`. Not a real DHU capture. |
| 1.3 | Default teal — DHU light mode | `dhu/1.3_visual_dhu_light.png` | HAS | DHU screenshot cropped to app pane (1832x1056). Surface renders dark gray (NavigationTemplate surface not initialized — see notes). |
| 1.4 | Default teal — DHU dark mode | — | BLOCKED | DHU `day`/`night` commands do not toggle `isDarkMode` (confirmed via logcat). Requires real vehicle or different DHU config. |
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
| 2.2 | Populated conversation (mock data) | `dhu/2.2_lead_agent_populated.png` | HAS | 3 mock messages from `createWithMockData()`. Real DHU capture, cropped to app pane. |
| 2.3 | Max messages (100) | — | MISSING | Verify scroll/truncation at `MAX_MESSAGES_PER_TAB = 100`. |

**Source**: `VanPilotScreen.kt` lines 118-121, 141-169.
**Mock data**: `ConversationTabManager.kt` lines 33-42 — 3 lead agent messages.

---

## 3. Sub-Agent Tabs (ListTemplate)

Each sub-agent gets its own tab. Maximum 2 sub-agent tabs (4 tabs total limit).

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 3.1 | Single sub-agent — "Researcher" | `dhu/3.1_researcher_messages.png` | HAS | 2 mock messages for "researcher" agent. Real DHU capture, cropped to app pane. |
| 3.2 | Second sub-agent — "Coder" | `dhu/3.2_coder_messages.png` | HAS | 1 mock message for "coder" agent. Real DHU capture, cropped to app pane. |
| 3.3 | Sub-agent with empty conversation | — | MISSING | "No messages yet" placeholder. |

**Source**: `VanPilotScreen.kt` lines 93-105, 122-127.
**Mock data**: `ConversationTabManager.kt` lines 45-62 — researcher (2 msgs), coder (1 msg).

---

## 4. Tab Bar States

The `TabTemplate` shows up to 4 tabs. Tab switching changes the active tab highlight
and swaps the content area.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 4.1 | Visual tab selected (default) | `dhu/4.1_visual_tab_selected.png` | HAS | Visual tab active, others inactive. Real DHU capture, cropped to app pane. |
| 4.2 | Lead Agent tab selected | `dhu/4.2_lead_agent_tab_selected.png` | HAS | Lead Agent tab active, content = message list. Real DHU capture, cropped to app pane. |
| 4.3 | Sub-agent tab selected | `dhu/4.3_sub_agent_tab_selected.png` | HAS | Researcher tab active. Real DHU capture, cropped to app pane. |
| 4.4 | All 4 tabs visible | `dhu/4.4_all_four_tabs.png` | HAS | Visual + Lead + 2 sub-agents at max capacity. Real DHU capture, cropped to app pane. |
| 4.5 | 2 tabs only (no sub-agents) | — | MISSING | Only Visual + Lead Agent when no sub-agents registered. |
| 4.6 | Stale tab fallback | — | MISSING | `activeTabId` not in `validTabIds` — falls back to Visual. |

**Source**: `VanPilotScreen.kt` lines 63-135 — `onGetTemplate()`.

---

## 5. Connection State Indicators

The `ConnectionState` enum defines visual indicators for connectivity. Per AC-9.2,
a disconnect indicator should be visible in the tab bar when offline.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 5.1 | Connected (no indicator) | — | BLOCKED | Normal state — no disconnect badge. Blocked on PR #139. |
| 5.2 | Disconnected indicator | — | BLOCKED | `showDisconnectIndicator = true`. Blocked on PR #139. |
| 5.3 | Reconnecting indicator | — | BLOCKED | Same visual as disconnected per current enum. Blocked on PR #139. |

**Source**: `ConnectionState.kt` lines 14-29.
**Note**: Connection indicator UI is being added in PR #139. Goldens blocked until that merges.

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

## 7. Dark Mode Transitions

Android Auto can toggle dark mode via configuration change. `onGetTemplate()` reads
`carContext.isDarkMode` on every refresh.

| # | State | File | Status | Notes |
|---|-------|------|--------|-------|
| 7.1 | Light to Dark transition | — | BLOCKED | DHU `day`/`night` commands do not toggle `isDarkMode`. |
| 7.2 | Dark to Light transition | — | BLOCKED | Same as 7.1. |

**Source**: `VanPilotScreen.kt` lines 36-39, 67.

---

## Summary

| Category | Total States | HAS | GENERATED | BLOCKED | MISSING |
|----------|-------------|-----|-----------|---------|---------|
| Visual Card Tab | 6 | 1 | 2 | 1 | 2 |
| Lead Agent Tab | 3 | 1 | 0 | 0 | 2 |
| Sub-Agent Tabs | 3 | 2 | 0 | 0 | 1 |
| Tab Bar States | 6 | 4 | 0 | 0 | 2 |
| Connection States | 3 | 0 | 0 | 3 | 0 |
| Surface Lifecycle | 3 | 1 | 0 | 0 | 2 |
| Dark Mode Transitions | 2 | 0 | 0 | 2 | 0 |
| **Total** | **26** | **9** | **2** | **6** | **9** |

### Priority for capture

1. **P0 — Core states** (must have before any PR review is meaningful):
   - ~~1.3~~ DONE, 1.4 BLOCKED (DHU teal, light/dark)
   - ~~2.2~~ DONE (lead agent with messages)
   - ~~3.1~~ DONE (sub-agent with messages)
   - ~~4.4~~ DONE (all 4 tabs visible)

2. **P1 — Edge cases** (important for regression):
   - 1.5 (bitmap displayed — requires gRPC `displayBitmap()` call)
   - 2.1 (empty conversation — app always loads mock data)
   - 4.5 (2 tabs only — app always loads with 4 tabs from mock data)

3. **P2 — Advanced** (nice to have):
   - Connection indicators (blocked on PR #139)
   - Surface size variations (needs different emulator config)
   - Dark mode transitions (BLOCKED — DHU day/night commands don't toggle isDarkMode)

### Known limitation: dark mode

The DHU `day` and `night` console commands trigger a `CarConfiguration` refresh but
do **not** change the `isDarkMode` flag reported to the app. Logcat confirms
`isDarkMode=false` after both `day` and `night` commands. This blocks captures for
states 1.4, 7.1, and 7.2. A real vehicle or different DHU configuration may be required.
