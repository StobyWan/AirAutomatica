# Live Dashboard

The AIRAUTOMATICA dashboard is a real-time flight console served at `GET /dashboard`. It is **read-only** and non-flight-critical: it displays telemetry, detections, and system state but does not send commands to the flight controller.

## Overview

- **Tech:** Plain HTML/CSS/JS with Tailwind CSS and Socket.IO. No React/Vue or heavy frameworks.
- **Updates:** Socket.IO pushes health, state, detections, sessions (1s), and events, path, trends (5s).
- **Initial load:** Fetches `/recent-events` and `/sessions` on connect for faster first paint.
- **Mobile-friendly:** Responsive layout; works on phones, tablets, and laptops.
- **Pi-friendly:** Lightweight; no heavy map or chart libraries.

## Panels

### System Health

Telemetry status badge, backend info, heartbeat age, reconnect count, last disconnect reason.

When serial telemetry is connected, an **Autopilot Capabilities** subsection appears: firmware name (e.g. ArduPilot, INAV), profile ID, capability chips (params_read, params_write, command_long, message_interval, missions, guided, rc_over_mavlink) each with check or cross, optional notes, and any downgrade_reasons (e.g. "parameter read probe timeout"). This banner is hidden when `capabilities` is absent (e.g. mock mode).

### Aircraft State

Mode, lat/lon, altitude, heading (with compass), voltage, current, groundspeed, airspeed.

### Flight Path

SVG plot of recent flight breadcrumb (from `path_points` or `telemetry_samples`), current position (green), and detection markers (red). Uses relative coordinates; degrades to "No path data" when empty.

### Trends

Four sparklines: voltage, rel_alt_m, groundspeed_m_s, heartbeat_age_s. Data from `telemetry_samples` (DB) and in-memory heartbeat buffer. Degrades to "No trend data" when empty.

### AI HAT (optional)

In the Connection & Health card: capability and one-shot detection. Shows Backend (Hailo/None), Hardware detected, Device, State, Threshold. **Run one-shot detection** triggers one-shot detection. **AI HAT last one-shot** shows cached result with stale age (e.g. "person, car (2) — 18s ago"). Distinct from persisted detection history (see below). See [ai_hat.md](ai_hat.md).

### Recent Detections

Persisted detection history from mission-flow (Ollama/mock), AI HAT recording-time (source `ai_hat_recording`), and AI HAT one-shot when session active (source `aihat`). Card layout with label, confidence, summary, timestamp, source_backend, lat/lon, rel_alt_m. Newest first. Empty state when no detections. Source shown per card. AI HAT last one-shot is cached separately for quick display.

### Event Log

Recent system events: `telemetry_status_transition`, `app_shutdown`, etc. Newest first, limit 20 visible. Degrades when persistence disabled.

### Session History

Recent flight sessions with started_at, ended_at, duration (computed client-side), detection_count. Links to session detail page. Newest first.

### Settings

Configure telemetry, AI provider, AI HAT, and mission logic. Grouped into:

- **Telemetry**: Backend (mock/serial), serial port, baud rate. Default port `/dev/ttyUSB0` for CP2102/USB-TTL; `/dev/ttyACM0` for native USB.
- **AI Provider**: mock or ollama. Ollama URL/model/timeout shown when ollama selected.
- **AI HAT**: Additive checkbox; runs alongside the selected provider on Pi 5, not instead of it.
- **Advanced** (collapsible): Min confidence, duplicate window.

Settings are saved to `~/.airautomatica/settings.json`. Some apply immediately (live); others require reconnect or app restart. The UI shows apply hints per section and uses canonical keys only (`LOCAL_LLM_PROVIDER`, `AI_HAT_ENABLED`, etc.).

### Settings that apply live (no restart)

- **CAMERA_RECORDING_MODE** — RecordingAutoController reads on each call
- **SESSION_AUTO_START_ON_ARM** — SessionAutoController reads on each call
- **AI_SCHEDULER_COOLDOWN_SEC** — AiInferenceScheduler reads on each cooldown
- **AI_MIN_CONFIDENCE** — MissionLogic.reconfigure() when MissionLogic is available
- **AI_DUPLICATE_WINDOW_SEC** — MissionLogic.reconfigure() when MissionLogic is available
- **AI subsystem (when hot-reload is available)** — `LOCAL_LLM_PROVIDER`, `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_TIMEOUT`, `OLLAMA_NUM_THREAD` apply immediately via AI subsystem hot-reload, without restart
- **Telemetry (when reconnect is available)** — `TELEMETRY_BACKEND`, `SERIAL_PORT`, `SERIAL_BAUD` apply immediately via telemetry reconnect, without restart

**AI subsystem hot-reload:** When the runtime holder is available (normal app startup), changing AI provider/model/URL/timeout/threads triggers a reload of the active AI and task services. The new services are swapped in atomically; MissionLogic and API handlers use the updated services on the next request. If reload fails (e.g. provider change mock↔ollama, or Ollama unreachable), the old services remain active and the save response reports the failure truthfully. Provider changes require a full app restart.

**Telemetry reconnect:** When the telemetry controller is available (normal app startup), changing backend/port/baud stops the current telemetry source, creates a new one from the updated config, and restarts the loop. Serial port is validated before reconnect (must exist on Unix); invalid config fails fast with a clear error. If reconnect fails, the old source is restarted and the save response reports the failure truthfully.

**Phase 5 UX:** The settings UI shows progress during save (e.g. "Saving… (reconnecting telemetry)") when telemetry or AI subsystem changes are being applied. After save, the active backend and provider are displayed (e.g. "Telemetry: mock · AI: mock").

When MissionLogic is unavailable (e.g. in some test setups), AI_MIN_CONFIDENCE and AI_DUPLICATE_WINDOW_SEC take effect after reconnect support or restart.

## Data Sources

| Panel         | Source                                      |
|---------------|---------------------------------------------|
| System Health | health_update                               |
| Aircraft State| state_update                                |
| Flight Path   | telemetry_path_update (path_points, state)  |
| Trends        | trends_update (telemetry_samples, buffer)   |
| Detections    | detections_update                           |
| Event Log     | events_update (system_events)               |
| Session History| sessions_update (flight_sessions + count)  |

## Socket.IO Events

| Event                   | Interval | Payload                          |
|-------------------------|----------|----------------------------------|
| health_update           | 1s       | status, telemetry, persistence, capabilities (optional: firmware_name, profile_id, supports_*, notes, downgrade_reasons) |
| state_update            | 1s       | aircraft state                   |
| detections_update       | 1s       | detections, session_id           |
| sessions_update         | 1s       | sessions (with detection_count)  |
| events_update           | 5s       | events                           |
| telemetry_path_update   | 5s       | path, current_position, detections |
| trends_update           | 5s       | voltage, rel_alt_m, groundspeed_m_s, heartbeat_age_s |

## Read-Only Nature

The dashboard does not expose command-back controls. It only displays data. Use the API or other tools for any control operations.

## See also

- [persistence.md](persistence.md) — Session data, path points, telemetry samples
- [preprocessing.md](preprocessing.md) — Telemetry preprocessing and debrief
- [packaging.md](packaging.md) — Apply modes, settings precedence
