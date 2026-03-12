# Raspberry Pi 5 Setup

This document covers setup for AirAutomatica on Raspberry Pi 5, including prerequisites for Ollama mode.

## Prerequisites for Ollama Mode

When using `LOCAL_LLM_PROVIDER=ollama` (the default for development bootstrap), Ollama must be installed, running, and have the model available. The app does not install or start Ollama automatically.

1. **Install Ollama** — Follow [https://ollama.com](https://ollama.com) (Linux: `curl -fsSL https://ollama.com/install.sh | sh`).

2. **Pull the model** — Run `ollama pull <model>` where `<model>` matches `LOCAL_LLM_MODEL` (default `gemma3:1b`). Or `make setup-ollama` from the repo root.

3. **Enable Ollama on boot** — On Linux, Ollama's installer typically adds a systemd service. Ensure it is enabled:
   ```bash
   sudo systemctl enable ollama
   sudo systemctl start ollama
   ```

4. **Verify** — `curl http://127.0.0.1:11434/api/tags` should return a list of models.

Without these steps, the app will start but AI features will return fallback results when Ollama is unreachable.

## Ollama degraded mode

If provider is ollama and readiness fails at startup:

- The app still starts
- `/health` reports `ollama_ready: false`
- AI routes return fallback output
- No automatic retries beyond startup wait (unless implemented elsewhere)

This is intentional unless fail-fast mode is enabled. Set `OLLAMA_REQUIRED=1` (or `AIRAUTOMATICA_OLLAMA_REQUIRED=1`) to make startup fail when Ollama is not ready. Precedence: `AIRAUTOMATICA_OLLAMA_REQUIRED` overrides `OLLAMA_REQUIRED`.

Model must match `LOCAL_LLM_MODEL`. The provisioning script only guarantees Ollama setup when run with `--with-ollama`.

## Bootstrap Script

For development on Pi 5, run the bootstrap script:

```bash
bash scripts/setup_airautomatica_pi5.sh
```

This installs tools, clones the repo, creates a venv, and sets `LOCAL_LLM_PROVIDER=ollama` in `.env`. It does **not** install Ollama by default.

To install Ollama, pull the model (from `LOCAL_LLM_MODEL`), and enable the Ollama systemd service in one step:

```bash
bash scripts/setup_airautomatica_pi5.sh --with-ollama
```

Without `--with-ollama`, run `make setup-ollama` (or install Ollama manually) after bootstrap if you want local AI. Provisioning and runtime both use `LOCAL_LLM_MODEL`; app config is the canonical source of truth.

## Packaged Install (.deb)

For packaged installs, see [packaging.md](packaging.md). The default is mock mode; switching to Ollama requires the prerequisites above and editing `/etc/airautomatica/airautomatica.env`.
