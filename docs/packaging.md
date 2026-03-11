# Linux Packaging

AirAutomatica can be installed as a systemd-managed service on Debian and Raspberry Pi OS.

## Default Packaged Behavior

Packaged installs start in **mock mode** by default:

- `TELEMETRY_BACKEND=mock` — no flight controller required
- `LOCAL_LLM_PROVIDER=mock` — no Ollama required
- `CAMERA_RECORDING_MODE=manual` — camera recording off by default

This ensures the service starts cleanly after install, is demoable immediately, and does not fail if `/dev/ttyUSB0` or Ollama are missing.

To switch to real hardware, edit `/etc/airautomatica/airautomatica.env` and restart the service.

## Config Precedence

1. **`/etc/airautomatica/airautomatica.env`** — main operator-editable config for packaged installs (deployment wiring: telemetry, serial, Ollama, camera mode)
2. **`~/.airautomatica/settings.json`** — loaded by the app for dashboard/runtime tweaks
3. **Internal defaults** — in config.py when neither above sets a value

Use the env file for deployment configuration; settings.json remains for dashboard-driven changes.

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
- **Python 3.12**: Raspberry Pi OS Bookworm ships Python 3.11. Use Trixie, or install python3.12 from testing/backports.
- **Ollama**: For system service, Ollama must run as a separate service reachable at `LOCAL_LLM_BASE_URL`.
- **Camera recording**: Requires `rpicam-vid` (modern Raspberry Pi OS) or `libcamera-vid` (legacy rpicam-apps). Not a package dependency.
