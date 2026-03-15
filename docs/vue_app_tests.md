# Vue App Test Recommendations

Legacy Dashboard V1 (server-rendered HTML) and `tests/test_dashboard.py` have been removed. The dashboard is now Vue SPA–only. This document maps the former server-side UI tests to recommended Vue/frontend tests.

## Removed Coverage (Legacy)

| Legacy Test | What It Asserted |
|-------------|------------------|
| `test_dashboard_route_exists` | GET /dashboard returns 200, HTML with AIRAUTOMATICA, "dashboard" |
| `test_session_detail_route_exists` | GET /dashboard/sessions/1 returns 200, HTML with "path-list" |
| `test_session_detail_includes_debrief_section` | Debrief section IDs, Generate/Regenerate AI Summary buttons |
| `test_dashboard_includes_ai_observability_rate_labels` | `perception_acceptance_rate`, `telemetry_meaningful_rate` in health fields |
| `test_dashboard_settings_uses_canonical_keys` | LOCAL_LLM_PROVIDER, AI_HAT_ENABLED; no AI_MODE; Telemetry, AI Provider, AI HAT, Advanced sections |
| `test_dashboard_includes_camera_recording_controls` | camera-start-btn, camera-stop-btn, video-state-badge, Live Camera Controls |

## Recommended Vue Tests to Add

### 1. Routing & Layout

- **DashboardView** renders when route is `/dashboard` (or base path)
- **SessionDetailView** renders when route is `/dashboard/sessions/:id`
- **SettingsView** renders when route is `/dashboard/settings`
- **SessionHistoryView** renders when route is `/dashboard/history`
- **DashboardNav** shows Live, Session History, Settings tabs

### 2. Dashboard Live Tab

- **ConnectionHealth** shows connection status badge
- **OperationsHud** shows session start/stop, camera start/stop buttons
- **LiveCameraFeed** or camera controls present when on Live tab
- **QuickTelemetry** shows voltage, altitude, speed, etc. when connected

### 3. Settings View

- **Canonical keys**: `LOCAL_LLM_PROVIDER`, `AI_HAT_ENABLED`, `OLLAMA_NUM_THREAD` present; no `AI_MODE`
- **Sections**: Telemetry, AI Provider, AI HAT, Advanced (collapsible)
- **Save** triggers API call with canonical keys only

### 4. Session Detail View

- **Debrief section** with Generate/Regenerate AI Summary buttons
- **Path/Replay** area when session has path data
- **Recordings** list when session has recordings
- **Replay tab** lazy-loads data only when opened

### 5. Health & Observability

- **ConnectionHealth** or equivalent displays `perception_acceptance_rate`, `telemetry_meaningful_rate` when available from `/health` or socket

### 6. Component-Level (Unit)

- **formatters** (`@/utils/formatters`) — `fmt`, `fmtTs`, `formatDistance`, `fmtSourceBackend`, `labelMode`, etc.
- **pathPlot** (`@/utils/pathPlot`) — SVG path rendering
- **sparklines** (`@/utils/sparklines`) — trend data for charts
- **Replay utils** (`replayUtils.ts`) — `findIndexForTimestamp`, `precomputeChartData`, `selectPrimaryRecording`, `formatOffsetMs` (already covered)

### 7. Store & API

- **Connection store** — fetchState, disconnect, mode changes
- **Sessions store** — list sessions, current_session_id
- **Settings store** — load, save, apply modes
- **Replay store** — load, seek, play/pause, chartData (lazy load, session change reset)

## Implementation Notes

- Use **Vitest** + **@vue/test-utils** for component and unit tests
- Mock API calls via `vi.mock('@/api/...')` or MSW
- For routing tests, use `createRouter` with a test base path or `createMemoryHistory`
- Replay tests already exist in `frontend/src/components/replay/replayUtils.test.ts`, `replaySeek.test.ts`, `ReplayTab.lazy.test.ts`

## Priority Order

1. **High**: Settings canonical keys, Replay store/reset, Session detail debrief
2. **Medium**: Routing, Dashboard nav, Live tab camera controls
3. **Lower**: Formatters/pathPlot/sparklines (pure functions, low regression risk)
