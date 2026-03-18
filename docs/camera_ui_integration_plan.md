# Camera UI Integration Plan (Refined)

## One-Sentence Guidance

**Implement truthful camera awareness across health, status API, and dashboard UI, but keep durable camera source changes in Settings unless live switching is already fully supported.**

---

## Design Principles

1. **Backend truth first** → lightweight health flow → UI rendering off real state
2. **Split full status from health**: Health answers *what is selected now, what is available now, what is safe to show now*. Status endpoint answers *what cameras exist, what capabilities they have, what the UI needs for deeper rendering*.
3. **Dashboard selection is read-only**: Show discovered cameras and current resolved camera. Actual source changes happen in SettingsView only. Do not imply live switching.
4. **Configured vs Resolved**: Distinguish clearly in UI wording:
   - **Configured camera**: Auto or specific source ID (from settings)
   - **Active camera**: Resolved descriptor, e.g. "Logitech C270, USB" or "CSI Camera 0"
5. **Single shared capability helper**: Centralize camera-specific state. No duplicated logic in publisher and router.
6. **Truthful schemas**: Do not invent state (e.g. `preview_active`, `last_error`) unless truly tracked. Omit or make nullable.
7. **One shared frontend fetch**: Camera status fetched once on mount/view activation, stored centrally, components consume. No per-component fetches.

---

## Backend

### 1. Shared Camera Status Helper

**New file:** `src/airautomatica/camera/status.py`

Single module that answers:

- `selected_descriptor` (from CameraSelector)
- `selected_label`, `selected_kind` (derived from descriptor)
- `still_capture_available` (csi or usb argv non-None for selected descriptor)
- `recording_available`, `preview_available` (delegate to recording service / existing logic)

Expose something like:

```python
def get_camera_status_summary(
    registry: CameraRegistry,
    selector: CameraSelector,
    recording_service: CameraRecordingService | None,
) -> dict
```

Returns lightweight dict for health and full dict for status endpoint. **Do not duplicate** `is_still_capture_available` in publisher and router; call this helper.

### 2. GET /camera/status Endpoint

**File:** `src/airautomatica/api/routers/camera.py`

- `GET /camera/status` returns:
  - `cameras`: list of `{ id, display_name, source_type, is_selected }`
  - `configured_source_id`: from settings (empty = Auto)
  - `configured_auto_fallback`: from settings
  - `active_camera_id`, `active_camera_label`, `active_camera_kind`: resolved descriptor
  - `preview_available`, `recording_available`, `still_capture_available`
  - `recording_active`: from recording service
  - Omit `preview_active` unless truly tracked. Omit `last_error` unless we have a real source.

Uses shared status helper. Triggers `registry.refresh()` on request (full discovery).

### 3. Extend Health Payload (Lightweight)

**File:** `src/airautomatica/realtime/publisher.py`

Add to health when camera service present (via shared helper):

- `active_camera_id`, `active_camera_label`, `active_camera_kind`
- `still_capture_available`
- `configured_source_id` (optional; can come from settings getter)

**Do not** run full registry discovery in publisher. Use selector + recording service only. Still capture availability: call shared helper (which only checks argv builders, no subprocess).

---

## Frontend

### 4. API and Types

**File:** `frontend/src/api/camera.ts`

- `getCameraStatus(): Promise<CameraStatusResponse>`

**File:** `frontend/src/types/socket.ts`

- Extend `HealthUpdatePayload`: `active_camera_id?`, `active_camera_label?`, `active_camera_kind?`, `still_capture_available?`

**File:** `frontend/src/types/api.ts` (or inline in camera.ts)

- `CameraStatusResponse`: cameras, configured_source_id, active_camera_*, preview_available, recording_available, still_capture_available, recording_active

### 5. Shared Camera State

**New store or extend health store:** `frontend/src/stores/camera.ts` (or add to existing store)

- One fetch of `getCameraStatus()` on dashboard mount or when entering live view
- Store result; components consume via store
- No per-component fetches of `/camera/status`

### 6. LiveCameraFeed

**File:** `frontend/src/components/LiveCameraFeed.vue`

- Show **active camera** label: "Active camera: {active_camera_label or '—'}"
- Show **discovered cameras** list (from store) when available; **read-only** display
- Link to Settings for changing camera source: "Change camera in Settings"
- Handle: no cameras, one camera, multiple cameras
- Improve error states: "No cameras found", "Preview unavailable (recording active)", "Turn on Camera Ready"
- Do **not** add a dropdown that changes selection (read-only)

### 7. ConnectionHealth

**File:** `frontend/src/components/ConnectionHealth.vue`

- Disable one-shot when `!still_capture_available`
- Disable when `camera_recording` (already done)
- Show: "Active camera: {label}" when available
- Improve error display for detection failures
- Prevent duplicate clicks (already has `aiDetectLoading`)

### 8. AiTab

**File:** `frontend/src/components/AiTab.vue`

- Add one-shot detection control: button, pending/success/failure states
- Disable when recording or `!still_capture_available`
- Show result clearly (detections or error)

### 9. OperationsHud

**File:** `frontend/src/components/OperationsHud.vue`

- Add compact chip: "Camera: {active_camera_label or 'Auto'}" from health
- Or: "Configured: Auto · Active: CSI Camera 0" when both available

### 10. SettingsView

**File:** `frontend/src/views/SettingsView.vue`

- In Camera Recording section, add:
  - `CAMERA_SOURCE_ID`: select (populated from discovered cameras) or text input; empty = Auto
  - `CAMERA_SOURCE_AUTO_FALLBACK`: checkbox
- Add to form and `SETTINGS_KEYS` / `CHECKBOX_KEYS`

**File:** `frontend/src/constants/settings.ts`

- Add `CAMERA_SOURCE_ID`, `CAMERA_SOURCE_AUTO_FALLBACK`

---

## Phase Scope: What This Does NOT Do

- **No live camera switching from dashboard**: Selection changes only via Settings; restart may be required.
- **No `preview_active`** unless we implement real tracking.
- **No `last_error`** unless we have a real source.
- **No dropdown in LiveCameraFeed** that persists a new selection.

---

## Tests

- Backend: `test_camera_status_endpoint` (no cameras, one, multiple, configured vs active, still_capture_available)
- Backend: `test_health_includes_camera_status` (active_camera_*, still_capture_available)
- Backend: `test_camera_status_helper` (shared module)
- Frontend: Component tests for disabled states, read-only display
- API: Camera status response shape

---

## Execution Order

1. Backend: shared camera status helper
2. Backend: GET /camera/status
3. Backend: extend health payload
4. Frontend: API client, types, store
5. Frontend: LiveCameraFeed (read-only)
6. Frontend: ConnectionHealth, AiTab, OperationsHud
7. Frontend: SettingsView camera source
8. Tests
