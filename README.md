# AIRAUTOMATICA

[![CI](https://github.com/StobyWan/AirAutomatica/actions/workflows/ci.yml/badge.svg)](https://github.com/StobyWan/AirAutomatica/actions/workflows/ci.yml)
[![Docker](https://github.com/StobyWan/AirAutomatica/actions/workflows/docker.yml/badge.svg)](https://github.com/StobyWan/AirAutomatica/actions/workflows/docker.yml)

Companion computer app for Raspberry Pi 5 that reads MAVLink telemetry from an ArduPilot flight controller over serial/USB, maintains shared aircraft state, and exposes a local FastAPI server. Designed for future onboard AI perception (Raspberry Pi AI HAT+); today it runs in mock or Ollama mode for development.

**Disclaimer:** This software is **not flight-critical**. It does not send commands to the flight controller. It reads telemetry and logs detections. Use at your own risk.

## What Works Today

- **Mock mode**: Simulated telemetry and AI. No hardware. Run locally for development.
- **Ollama mode**: Local LLM via [Ollama](https://ollama.com/) simulates perception-style outputs. Useful for testing mission logic.
- **Serial MAVLink mode**: Real telemetry from ArduPilot over USB/serial (Matek F405-WING, CP2102, etc.).
- **API**: `/health`, `/state`, `/recent-detections`. SQLite persistence for sessions and detections.
- **Live Dashboard**: Real-time UI at `GET /dashboard` with Socket.IO updates (health, state, detections, session history). Session detail pages show flight path (lat/lon). Read-only, non-flight-critical. Works with persistence disabled.
- **Graceful shutdown**: Ctrl+C ends session cleanly.

## What Is Mock vs Real

| Component | Mock | Real |
|-----------|------|------|
| Telemetry | Simulated orbit/state | MAVLink over serial |
| AI | Deterministic fake or Ollama | Raspberry Pi AI HAT+ (scaffold only) |
| Persistence | SQLite (optional) | Same |

AI HAT mode exists as a scaffold; real Hailo integration is not yet implemented.

## Quick Start (Mock Mode)

No hardware or `.env` needed:

```bash
git clone https://github.com/StobyWan/AirAutomatica.git
cd AirAutomatica
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
python -m airautomatica.main
# or: uv run airautomatica
```

Then open `http://localhost:8000/health`, `http://localhost:8000/state`, or `http://localhost:8000/dashboard` for the live UI.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or standard venv

## Local Setup

```bash
# Clone (or navigate if you already have the repo)
git clone https://github.com/StobyWan/AirAutomatica.git
cd AirAutomatica

# Create venv and install (with uv)
uv venv
source .venv/bin/activate  # or: .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"

# Optional: Ollama for local AI (run make setup-ollama to install and pull default model)
# Or with standard venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

All settings come from environment variables. Copy `.env.example` to `.env` and override as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEMETRY_BACKEND` | `mock` | `mock` or `serial` |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial device (default for CP2102/FTDI; use `/dev/ttyACM0` for native USB) |
| `SERIAL_BAUD` | `921600` | Baud rate (57600 for telemetry radios) |
| `LOCAL_LLM_PROVIDER` | `ollama` | `ollama` or `mock` |
| `LOCAL_LLM_BASE_URL` | `http://127.0.0.1:11434` | Ollama API URL |
| `LOCAL_LLM_MODEL` | `gemma3:1b` | Ollama model name |
| `LOCAL_LLM_TIMEOUT` | `30` | Local LLM request timeout (seconds) |
| `AI_HAT_ENABLED` | `0` | Enable AI HAT layer alongside local LLM (additive; Pi 5) |
| `AI_MIN_CONFIDENCE` | `0.5` | Min confidence to persist detection (0–1) |
| `AI_DUPLICATE_WINDOW_SEC` | `30` | Seconds to suppress same-label duplicate |
| `AIHAT_MODEL_NAME` | `default` | AI HAT model (when AI HAT enabled) |
| `AIHAT_DEVICE` | `auto` | Placeholder; AI HAT+ uses HailoRT auto-discovery |
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API port |
| `SQLITE_DB_PATH` | `~/.airautomatica/airautomatica.db` | SQLite database path |

## Running

**Default** (Ollama for local AI):

```bash
# Install Ollama first: make setup-ollama
python -m airautomatica.main
# or: airautomatica
# or with uv: uv run airautomatica
```

**Mock mode** (no setup, no Ollama):

```bash
export TELEMETRY_BACKEND=mock
export LOCAL_LLM_PROVIDER=mock
python -m airautomatica.main
```

**Serial MAVLink mode** (Raspberry Pi with flight controller connected):

```bash
export TELEMETRY_BACKEND=serial
export SERIAL_PORT=/dev/ttyUSB0  # CP2102; use /dev/ttyACM0 for native USB
export SERIAL_BAUD=921600        # match FC

python -m airautomatica.main
```

The API server runs at `http://localhost:8000` by default. Ctrl+C and SIGTERM trigger graceful shutdown (session ended, loops stopped). See [docs/persistence.md](docs/persistence.md#shutdown) for details.

## Local Database

SQLite stores flight sessions, telemetry samples, detections, system events (including telemetry lifecycle transitions), and commands. Default path: `~/.airautomatica/airautomatica.db`. Set `SQLITE_DB_PATH` to override. WAL mode is used for better concurrent read/write. The database is optional; the app runs normally if it is unavailable. `GET /health` includes a `persistence` block with DB path, session ID, and last error if any. See [docs/persistence.md](docs/persistence.md).

## API Endpoints

| Endpoint | Description |
|----------|--------------|
| `GET /health` | Health check. When serial telemetry is connected, includes a `capabilities` block: `firmware_name` (ArduPilot, INAV, Unknown), `profile_id`, capability flags (`supports_params_read`, etc.), `notes`, and `downgrade_reasons` |
| `GET /state` | Current aircraft state (JSON) |
| `GET /recent-detections` | Recent persisted detections (current session, limit 20) |
| `GET /recent-events` | Recent system events for dashboard |
| `GET /sessions` | Recent flight sessions with detection counts |
| `GET /sessions/{id}/path` | Flight path JSON (lat, lon, rel_alt_m, timestamp) |
| `GET /sessions/{id}/telemetry-samples` | Recent telemetry samples for path/sparklines |
| `GET /settings` | Current settings (telemetry, AI, serial, etc.) |
| `POST /settings` | Save settings (restart required to apply) |
| `GET /dashboard` | Real-time flight dashboard (HTML + Socket.IO) |
| `GET /dashboard/sessions/{id}` | Session detail page with flight path (lat/lon) |

## Live Dashboard

`GET /dashboard` serves a real-time UI. Open `http://<host>:8000/dashboard` from a phone, tablet, or laptop on the same network.

**Features:**
- **System Health** — Telemetry status, backend info, heartbeat age, reconnect count. When connected, **Autopilot Capabilities** shows detected firmware (ArduPilot/INAV/Unknown), profile ID, capability chips (params_read, guided, etc.), notes, and any downgrade reasons from probes.
- **Aircraft State** — Mode, lat/lon, altitude, heading (with compass), voltage, speed
- **Flight Path** — SVG plot of recent flight breadcrumb, current position, and detection markers
- **Trends** — Sparklines for voltage, altitude, groundspeed, heartbeat age
- **Recent Detections** — Card layout with label, confidence, summary, timestamp, position, source
- **Event Log** — Recent system events (telemetry lifecycle, app shutdown)
- **Session History** — Sessions with duration, detection count; click to view path
- **Session Detail** — `GET /dashboard/sessions/{id}` shows the flight path (lat/lon points) for a session
- **Settings** — Configure telemetry backend, AI mode, serial port, Ollama URL/model, etc. Saves to `~/.airautomatica/settings.json`; restart required to apply

Uses Socket.IO for live updates. Read-only, non-flight-critical. Works with persistence disabled. See [docs/dashboard.md](docs/dashboard.md) for details.

## Project Structure

```
src/airautomatica/
├── main.py              # Entry point, backend selection
├── config.py            # Configuration from env
├── logging_config.py    # Logging setup
├── models/
│   └── state.py         # AircraftState model
├── telemetry/
│   ├── base.py          # Telemetry interface
│   ├── mock.py          # Mock telemetry for dev
│   ├── mavlink_parser.py # MAVLink normalization layer
│   ├── mavlink_telemetry.py
│   ├── serial_mavlink.py # Serial MAVLink backend
│   ├── mavlink/
│   │   └── detection.py # Autopilot detection from HEARTBEAT
│   ├── capabilities/
│   │   └── profile.py  # CapabilityProfile, CapabilityInfo, downgrade constants
│   ├── adapters/
│   │   ├── base.py     # AutopilotAdapterProtocol
│   │   ├── ardupilot.py
│   │   ├── inav.py
│   │   └── generic.py
│   ├── transport/
│   │   └── ...
│   └── services/
│       └── vehicle_connection_manager.py
├── ai/
│   ├── service.py      # AiService interface
│   ├── models.py       # AiResult model
│   ├── mock_service.py # Mock AI for tests
│   ├── ollama_service.py  # Ollama (local LLM)
│   └── aihat_service.py   # Raspberry Pi AI HAT+ scaffold
├── db/
│   ├── base.py          # Engine, WAL, init
│   ├── models.py        # SQLAlchemy models
│   └── session.py       # Session context manager
├── services/
│   ├── state_store.py   # Shared in-memory state
│   ├── mission_logic.py # Mission logic (state + AI)
│   └── persistence.py  # PersistenceService, TelemetrySampler
├── api/
│   └── server.py       # FastAPI app
├── realtime/
│   ├── socketio_app.py # Socket.IO ASGI wrapper
│   └── publisher.py    # Dashboard event publisher
└── ui/
    ├── dashboard.py    # Dashboard HTML loader
    └── templates/
        ├── dashboard.html
        └── session_detail.html
```

See [ai_backends.md](ai_backends.md) for AI backend details and Raspberry Pi transition.

## Tests

```bash
pytest
# or with uv: uv run pytest
```

## Development

- **Install dev deps**: `uv pip install -e ".[dev]"` (or `pip install -e ".[dev]"`)
- **Format**: `make format` or `black src tests && isort src tests`
- **Lint**: `make lint` (black + isort check)
- **Typecheck**: `make typecheck`
- **Test**: `make test` or `pytest`
- **All checks**: `make check`

**Pre-commit** (optional): `pip install pre-commit && pre-commit install`

**Docker**: `docker build -t airautomatica . && docker run -p 8000:8000 airautomatica` — validate at http://localhost:8000/health

CI runs format, lint, typecheck, and tests on push/PR.

## Example Hardware / Bench Setup

See [docs/example_hardware.md](docs/example_hardware.md) for a documented reference setup: Matek F405-WING V2, Raspberry Pi 5, CP2102 USB-to-TTL adapter, and power components. It is an example only — the software works with other ArduPilot FCs and serial adapters.

## Future: Raspberry Pi Serial Mode

On Raspberry Pi:

1. Connect flight controller via USB (or CP2102/FTDI adapter).
2. Identify serial device: `ls /dev/ttyACM*` or `ls /dev/ttyUSB*` (CP2102/FTDI → `/dev/ttyUSB0`).
3. Add user to `dialout` group: `sudo usermod -a -G dialout $USER`.
4. Set `TELEMETRY_BACKEND=serial` and `SERIAL_PORT` accordingly.

See [docs/bench_first_test.md](docs/bench_first_test.md) for a first hardware bring-up checklist.

## Status and Roadmap

- **Current**: Mock and Ollama modes work. Serial MAVLink works with ArduPilot. Persistence, shutdown, and API are functional.
- **Next**: Raspberry Pi 5 bench validation; AI HAT+ Hailo integration (vision only).
- **Not planned**: Flight-critical command sending; LLM reasoning onboard.
