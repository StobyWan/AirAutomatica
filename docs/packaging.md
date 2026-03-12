# Linux Packaging

AirAutomatica can be installed as a systemd-managed service on Debian and Raspberry Pi OS.

## Default Packaged Behavior

Packaged installs start in **mock telemetry** by default:

- `TELEMETRY_BACKEND=mock` — no flight controller required
- `LOCAL_LLM_PROVIDER` — **unset by default**; app discovers Ollama at startup:
  - If Ollama is discovered and ready, uses Ollama
  - Otherwise falls back to mock
  - Set explicitly in env or settings.json to override (e.g. `LOCAL_LLM_PROVIDER=ollama`) — never persisted over user choice
- `CAMERA_RECORDING_MODE=manual` — camera recording off by default

This ensures the service starts cleanly after install, prefers Ollama when available (e.g. Raspberry Pi with Ollama installed), and does not fail if `/dev/ttyUSB0` or Ollama are missing.

To switch to real hardware, edit `/etc/airautomatica/airautomatica.env` and restart the service.

## Config Precedence

1. **`/etc/airautomatica/airautomatica.env`** — main operator-editable config for packaged installs (deployment wiring: telemetry, serial, Ollama, camera mode)
2. **`~/.airautomatica/settings.json`** — loaded by the app for dashboard/runtime tweaks
3. **Internal defaults** — in config.py when neither above sets a value

Use the env file for deployment configuration; settings.json remains for dashboard-driven changes.

### Raw vs Effective Settings

- **Raw settings** — what is persisted in settings.json or set in env (explicit values).

- **Effective settings** — runtime values including discovered defaults. When `LOCAL_LLM_PROVIDER` is unset, the app discovers Ollama at startup and uses it if ready; otherwise mock. This discovery is not persisted.

### Apply Modes (live / reconnect / restart)

Settings apply in different ways:

- **live** — apply immediately: `CAMERA_RECORDING_MODE`, `SESSION_AUTO_START_ON_ARM`, `AI_SCHEDULER_COOLDOWN_SEC`, `AI_MIN_CONFIDENCE`, `AI_DUPLICATE_WINDOW_SEC` (MissionLogic reconfigure when available); when AI hot-reload is available: `LOCAL_LLM_PROVIDER`, `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_TIMEOUT`, `OLLAMA_NUM_THREAD`; when telemetry reconnect is available: `TELEMETRY_BACKEND`, `SERIAL_PORT`, `SERIAL_BAUD`
- **reconnect** — require subsystem reload. AI and telemetry settings use hot-reload/reconnect when available.
- **restart** — require full app restart (e.g. AI HAT, or changing AI provider between mock and ollama)

**AI subsystem hot-reload:** When running the normal app (not test-only setups), AI provider/model/URL/timeout/thread settings are reloaded on save without restart. If reload fails (e.g. switching provider mock↔ollama, or Ollama unreachable), the old services stay active and the save response reports the failure.

**Telemetry reconnect:** When running the normal app, telemetry backend/port/baud settings are reapplied on save without restart. Serial port is validated before reconnect (must exist on Unix). The current telemetry source is stopped, a new one is created from the updated config, and the loop restarts. If reconnect fails (e.g. invalid port), the old source is restarted and the save response reports the failure.

See also [dashboard.md](dashboard.md) for settings UI and apply hints.

## Install Layout

| Path | Purpose |
|------|---------|
| `/opt/airautomatica/` | App installation (wheel + venv) |
| `/opt/airautomatica/venv/` | Python virtual environment (created on target during package install) |
| `/opt/airautomatica/wheels/` | Packaged wheel; installed into venv by postinst |
| `/etc/airautomatica/airautomatica.env` | Main config (systemd EnvironmentFile) |
| `/var/lib/airautomatica/` | Runtime data (home for system user) |
| `/var/lib/airautomatica/.airautomatica/settings.json` | User settings |
| `/var/lib/airautomatica/.airautomatica/airautomatica.db` | SQLite database |
| `/var/lib/airautomatica/.airautomatica/recordings/` | Camera recordings |
| `/etc/systemd/system/airautomatica.service` | systemd unit |

### Recordings Path

Camera recordings are stored in `/var/lib/airautomatica/.airautomatica/recordings/` by default. The postinst script creates this directory with correct ownership. The path is configured via `AIRAUTOMATICA_RECORDINGS_DIR` in `/etc/airautomatica/airautomatica.env`.

**For packaged installs, use an absolute path.** Relative paths resolve relative to the service `WorkingDirectory` (`/opt/airautomatica`) and can cause "file not found" when the app serves recordings. The env template sets `AIRAUTOMATICA_RECORDINGS_DIR=/var/lib/airautomatica/.airautomatica/recordings` explicitly.

## Install with Script

From the repo root:

```bash
sudo packaging/linux/install.sh
```

Then:

```bash
sudo systemctl start airautomatica
sudo systemctl status airautomatica
journalctl -u airautomatica -f
```

## Service Management

```bash
sudo systemctl start airautomatica
sudo systemctl stop airautomatica
sudo systemctl restart airautomatica
sudo systemctl status airautomatica
journalctl -u airautomatica -f
```

## Uninstall

```bash
sudo packaging/linux/uninstall.sh
```

To also remove data and config:

```bash
sudo packaging/linux/uninstall.sh --purge
```

## .deb Package

### Build Locally

From repo root:

```bash
./packaging/debian/build-deb.sh
```

Output: `airautomatica_<version>_all.deb`

Optional version override:

```bash
VERSION=0.1.0 ./packaging/debian/build-deb.sh
```

### Install .deb

```bash
sudo dpkg -i airautomatica_*.deb
sudo systemctl start airautomatica
```

The `.deb` packages the wheel and systemd unit only. The venv is **created on the target machine** during `postinst`, and the wheel is installed into it. This ensures the Python interpreter and dependencies match the target architecture (e.g. ARM on Raspberry Pi).

### Pi Upgrade (Makefile)

From the Pi (or any machine with the repo):

```bash
# Two-step: download, then upgrade
make pi-download-deb
make pi-upgrade-deb DEB=airautomatica_0.1.0_all.deb   # use filename from download

# One-step: download latest and upgrade
make pi-upgrade-latest
```

Optional overrides: `REPO=owner/repo` or `TAG=v0.1.0` for `pi-download-deb`.

### Tag Release Flow

Push a tag like `v0.1.0`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions will:

1. Build the .deb
2. Upload it as a workflow artifact
3. Create a GitHub Release and attach the .deb

## Prerequisites for Ollama Mode

Switching to `LOCAL_LLM_PROVIDER=ollama` requires Ollama to be **installed and running** on the system. The packaged install does not install or start Ollama.

Before editing the env file:

1. **Install Ollama** — [https://ollama.com](https://ollama.com) (Linux: `curl -fsSL https://ollama.com/install.sh | sh`).
2. **Pull the model** — `ollama pull gemma3:1b` (or the model name you configure).
3. **Enable on boot** — `sudo systemctl enable ollama && sudo systemctl start ollama`.

See [pi_setup.md](pi_setup.md) for full prerequisites.

### Ollama degraded mode

If provider is ollama and readiness fails at startup: the app still starts, `/health` reports `ollama_ready: false`, AI routes return fallback output, and there are no automatic retries beyond startup wait. Set `OLLAMA_REQUIRED=1` to make startup fail when Ollama is not ready. Model must match `LOCAL_LLM_MODEL`.

## Switching to Real Hardware

Edit `/etc/airautomatica/airautomatica.env`:

```
TELEMETRY_BACKEND=serial
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=921600
LOCAL_LLM_PROVIDER=ollama
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=gemma3:1b
OLLAMA_NUM_THREAD=4
CAMERA_RECORDING_MODE=auto
```

Then restart:

```bash
sudo systemctl restart airautomatica
```

## Caveats

- **Serial port**: User `airautomatica` is in the `dialout` group for `/dev/ttyUSB0` access.
- **Camera recording**: Requires `rpicam-vid` (modern Raspberry Pi OS) or `libcamera-vid` (legacy rpicam-apps), and ffmpeg. The full `rpicam-apps` package (not lite) is required for libav/mpegts piping. The .deb lists ffmpeg as a dependency. The service unit sets `PATH` and `SupplementaryGroups=video dialout` so the process has camera and serial device access. Without `SupplementaryGroups`, systemd may not pass the user's groups to child processes. In auto mode, a disarm debounce (default 2.5s) reduces false stops from telemetry jitter or brief disconnects; tune via `CAMERA_RECORDING_DISARM_DEBOUNCE_SEC`. **Restart the service or reboot** after install/upgrade.
- **Python 3.12**: Raspberry Pi OS Bookworm ships Python 3.11. Use Trixie, or install python3.12 from testing/backports.
- **Ollama**: For system service, Ollama must run as a separate service reachable at `LOCAL_LLM_BASE_URL`. Install Ollama, pull the model, and enable the Ollama systemd service before switching to `LOCAL_LLM_PROVIDER=ollama`. See [Prerequisites for Ollama Mode](#prerequisites-for-ollama-mode) above. The airautomatica unit has `After=ollama.service` and `Wants=ollama.service` so it starts after Ollama when both are installed; if Ollama is not installed, these references are harmlessly ignored by systemd.
