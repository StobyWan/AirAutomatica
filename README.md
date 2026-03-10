# AIRAUTOMATICA

[![CI](https://github.com/StobyWan/AirAutomatica/actions/workflows/ci.yml/badge.svg)](https://github.com/StobyWan/AirAutomatica/actions/workflows/ci.yml)
[![Docker](https://github.com/StobyWan/AirAutomatica/actions/workflows/docker.yml/badge.svg)](https://github.com/StobyWan/AirAutomatica/actions/workflows/docker.yml)

Companion computer app for Raspberry Pi 5 that reads MAVLink telemetry from an ArduPilot flight controller over serial/USB, maintains shared aircraft state, and exposes a local FastAPI server. Designed for future onboard AI perception (Raspberry Pi AI HAT+); today it runs in mock or LM Studio mode for development.

**Disclaimer:** This software is **not flight-critical**. It does not send commands to the flight controller. It reads telemetry and logs detections. Use at your own risk.

## What Works Today

- **Mock mode**: Simulated telemetry and AI. No hardware. Run locally for development.
- **LM Studio mode**: Local LLM simulates perception-style outputs. Useful for testing mission logic on macOS.
- **Serial MAVLink mode**: Real telemetry from ArduPilot over USB/serial (Matek F405-WING, CP2102, etc.).
- **API**: `/health`, `/state`, `/recent-detections`. SQLite persistence for sessions and detections.
- **Graceful shutdown**: Ctrl+C ends session cleanly.

## What Is Mock vs Real

| Component | Mock | Real |
|-----------|------|------|
| Telemetry | Simulated orbit/state | MAVLink over serial |
| AI | Deterministic fake or LM Studio | Raspberry Pi AI HAT+ (scaffold only) |
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

Then open `http://localhost:8000/health` and `http://localhost:8000/state`.

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
| `SERIAL_PORT` | `/dev/ttyACM0` | Serial device (e.g. `/dev/ttyUSB0` for CP2102; `/dev/ttyACM0` for native USB) |
| `SERIAL_BAUD` | `921600` | Baud rate (57600 for telemetry radios) |
| `AI_MODE` | `mock` | `mock`, `lmstudio`, or `aihat` (`AI_BACKEND` legacy) |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234` | LM Studio API URL |
| `LM_STUDIO_MODEL` | `local-model` | LM Studio model name |
| `AI_MIN_CONFIDENCE` | `0.5` | Min confidence to persist detection (0–1) |
| `AI_DUPLICATE_WINDOW_SEC` | `30` | Seconds to suppress same-label duplicate |
| `AIHAT_MODEL_NAME` | `default` | AI HAT model (when `AI_MODE=aihat`) |
| `AIHAT_DEVICE` | `auto` | Placeholder; AI HAT+ uses HailoRT auto-discovery |
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API port |
| `SQLITE_DB_PATH` | `~/.airautomatica/airautomatica.db` | SQLite database path |

## Running

**Mock mode** (default, no hardware needed):

```bash
export TELEMETRY_BACKEND=mock
export AI_MODE=mock
python -m airautomatica.main
# or: airautomatica
# or with uv: uv run airautomatica
```

**LM Studio mode** (local AI on macOS):

```bash
# Start LM Studio, load a model, enable local server
export AI_MODE=lmstudio
export LM_STUDIO_BASE_URL=http://localhost:1234
export LM_STUDIO_MODEL=your-model
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
| `GET /health` | Health check |
| `GET /state` | Current aircraft state (JSON) |
| `GET /recent-detections` | Recent persisted detections (current session, limit 20) |

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
│   └── serial_mavlink.py # Serial MAVLink backend
├── ai/
│   ├── service.py      # AiService interface
│   ├── models.py       # AiResult model
│   ├── mock_service.py # Mock AI for tests
│   ├── lmstudio_service.py # LM Studio (macOS dev)
│   └── aihat_service.py # Raspberry Pi AI HAT+ scaffold
├── db/
│   ├── base.py          # Engine, WAL, init
│   ├── models.py        # SQLAlchemy models
│   └── session.py       # Session context manager
├── services/
│   ├── state_store.py   # Shared in-memory state
│   ├── mission_logic.py # Mission logic (state + AI)
│   └── persistence.py  # PersistenceService, TelemetrySampler
└── api/
    └── server.py       # FastAPI app
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

## Future: Raspberry Pi Serial Mode

On Raspberry Pi:

1. Connect Matek flight controller via USB (or CP2102/FTDI adapter).
2. Identify serial device: `ls /dev/ttyACM*` or `ls /dev/ttyUSB*`.
3. Add user to `dialout` group: `sudo usermod -a -G dialout $USER`.
4. Set `TELEMETRY_BACKEND=serial` and `SERIAL_PORT` accordingly.

See [docs/bench_first_test.md](docs/bench_first_test.md) for a first hardware bring-up checklist.

## Status and Roadmap

- **Current**: Mock and LM Studio modes work. Serial MAVLink works with ArduPilot. Persistence, shutdown, and API are functional.
- **Next**: Raspberry Pi 5 bench validation; AI HAT+ Hailo integration (vision only).
- **Not planned**: Flight-critical command sending; LLM reasoning onboard.
