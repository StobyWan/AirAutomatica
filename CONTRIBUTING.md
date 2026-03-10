# Contributing

Thanks for your interest. This is an early-stage project.

## Getting Started

1. Clone: `git clone https://github.com/StobyWan/AirAutomatica.git && cd AirAutomatica`
2. Install: `uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"`
3. Run in mock mode: `python -m airautomatica.main`
4. Run tests: `pytest`

## Before Submitting

- Run `pytest` and ensure all tests pass
- Keep changes small and focused
- No flight-critical logic; this app reads telemetry and logs detections only

## Pull Requests

Open a PR with a clear description. For larger changes, open an issue first to discuss.
