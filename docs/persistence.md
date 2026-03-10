# Local Database (SQLite)

AirAutomatica optionally persists flight data to a local SQLite database. The database is **non-flight-critical**: the app runs normally if the database is unavailable or writes fail.

## Purpose

The local database stores:

- **Flight sessions** — Start/end times, telemetry and AI backend names
- **Telemetry samples** — Throttled position, altitude, heading, battery, speed (sampled at ~1 Hz)
- **Detections** — AI inference results (label, confidence, summary, position)
- **System events** — Logged events, including telemetry lifecycle transitions (reconnects, status changes)
- **Commands sent** — MAVLink or other commands (for future use)

No image or video blobs are stored.

## Telemetry Lifecycle Events

When `telemetry_status` changes (e.g. `connecting` → `connected`, `connected` → `stale`), a `system_events` row is written with `event_type = "telemetry_status_transition"`. Metadata includes `from`, `to`, and when relevant `reconnect_count` and `last_disconnect_reason`. Duplicate events are avoided when the status has not changed.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SQLITE_DB_PATH` | `~/.airautomatica/airautomatica.db` | Database file path |

For development, you can use a path in the project root, e.g. `./airautomatica.db`.

## WAL Mode

SQLite runs in [WAL (Write-Ahead Logging)](https://www.sqlite.org/wal.html) mode for better concurrent read/write performance.

## Graceful Degradation

- If database initialization fails (e.g. permission error, disk full), the app logs a warning and continues without persistence.
- All persistence methods catch exceptions, log, and return without raising.
- Mission logic and the API are unchanged when the database is unavailable.

## Health Endpoint

`GET /health` includes a `persistence` block:

| Field | Description |
|-------|-------------|
| `persistence_enabled` | Whether the DB engine is available |
| `sqlite_db_path` | Path to the database file (or `null` if disabled) |
| `session_id` | Current flight session ID (or `null`) |
| `last_persistence_error` | Last error message from a failed write (or `null`) |

## Schema Summary

| Table | Purpose |
|-------|---------|
| `flight_sessions` | Session metadata (started_at, ended_at, backends) |
| `telemetry_samples` | Throttled telemetry (lat, lon, alt, heading, voltage, etc.) |
| `detections` | AI results (label, confidence, summary, position) |
| `system_events` | Event log (level, type, message) |
| `commands_sent` | Command log (name, status) |

## Recent Detections

`GET /recent-detections` returns up to 20 most recent persisted detections for the current flight session (newest first). Useful for bench testing AI detection flow. Returns empty list when DB is disabled or no session exists.

## Shutdown

Ctrl+C and SIGTERM trigger graceful shutdown. The app logs "Shutdown requested", ends the current flight session (sets `ended_at`), and logs an `app_shutdown` system event. Background loops (telemetry, mission logic) stop cleanly. Shutdown is idempotent—repeated signals do not cause duplicate cleanup. `atexit` backs up session end if the async path does not run.
