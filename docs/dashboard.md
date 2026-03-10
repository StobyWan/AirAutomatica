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

### Recent Detections

Card layout with label, confidence, summary, timestamp, source_backend, lat/lon, rel_alt_m. Newest first. Empty state when no detections.

### Event Log

Recent system events: `telemetry_status_transition`, `app_shutdown`, etc. Newest first, limit 20 visible. Degrades when persistence disabled.

### Session History

Recent flight sessions with started_at, ended_at, duration (computed client-side), detection_count. Links to session detail page. Newest first.

### Settings

Configure telemetry, AI provider, AI HAT, and mission logic. Grouped into:

- **Telemetry**: Backend (mock/serial), serial port, baud rate. Default port `/dev/ttyUSB0` for CP2102/USB-TTL; `/dev/ttyACM0` for native USB.
- **AI Provider**: mock, ollama, or lmstudio (legacy). Ollama URL/model/timeout shown when ollama selected; LM Studio fields when lmstudio (legacy).
- **AI HAT**: Additive checkbox; runs alongside the selected provider on Pi 5, not instead of it.
- **Advanced** (collapsible): Min confidence, duplicate window.

Settings are saved to `~/.airautomatica/settings.json`; restart required to apply. The UI uses canonical keys only (`LOCAL_LLM_PROVIDER`, `AI_HAT_ENABLED`, etc.).

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
