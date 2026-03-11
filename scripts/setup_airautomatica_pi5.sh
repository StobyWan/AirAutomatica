#!/usr/bin/env bash
set -euo pipefail

APP_NAME="AirAutomatica"
REPO_URL="https://github.com/StobyWan/AirAutomatica.git"
BASE_DIR="$HOME/dev"
APP_DIR="$BASE_DIR/$APP_NAME"
ENV_FILE="$APP_DIR/.env"

echo "==> Updating Raspberry Pi OS packages..."
sudo apt update
sudo apt full-upgrade -y

echo "==> Installing baseline development tools..."
sudo apt install -y \
  git curl wget vim nano htop tree unzip tmux \
  build-essential pkg-config \
  python3 python3-pip python3-venv python3-full \
  sqlite3 libsqlite3-dev \
  avahi-daemon ca-certificates \
  ffmpeg
sudo apt install -y gh 2>/dev/null || true

echo "==> Ensuring user is in serial access groups..."
sudo usermod -aG dialout "$USER" || true
sudo usermod -aG tty "$USER" || true

mkdir -p "$BASE_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Make uv available in this shell
export PATH="$HOME/.local/bin:$PATH"

echo "==> Verifying installed tools..."
python3 --version
git --version
gh --version || true
uv --version

echo "==> Ensuring Python 3.12+ for virtual environment..."
PYTHON_SPEC=""
if uv python install 3.12 2>/dev/null; then
  PYTHON_SPEC="3.12"
elif python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
  PYTHON_SPEC="python3"
fi

if [ -z "$PYTHON_SPEC" ]; then
  echo
  echo "ERROR: AirAutomatica requires Python 3.12+."
  echo "Raspberry Pi OS Bookworm ships with Python 3.11."
  echo
  echo "Options:"
  echo "  1. Upgrade to Raspberry Pi OS Trixie (includes Python 3.13)"
  echo "  2. Install Python 3.12 manually, then re-run this script"
  echo
  exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
  echo "==> Cloning $APP_NAME into $APP_DIR ..."
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "==> Repo already exists, pulling latest changes..."
  git -C "$APP_DIR" pull --ff-only || true
fi

cd "$APP_DIR"

echo "==> Creating virtual environment..."
uv venv --python "$PYTHON_SPEC"

echo "==> Activating virtual environment and installing dependencies..."
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e ".[dev]"

if [ ! -f "$ENV_FILE" ] && [ -f "$APP_DIR/.env.example" ]; then
  echo "==> Creating .env from .env.example ..."
  cp "$APP_DIR/.env.example" "$ENV_FILE"
fi

if [ -f "$ENV_FILE" ]; then
  echo "==> Writing safe default settings into .env ..."
  python3 - <<'PY'
from pathlib import Path
env_path = Path(".env")
text = env_path.read_text() if env_path.exists() else ""

defaults = {
    "TELEMETRY_BACKEND": "mock",
    "LOCAL_LLM_PROVIDER": "ollama",
    "AI_HAT_ENABLED": "0",
    "API_HOST": "0.0.0.0",
    "API_PORT": "8000",
    "SQLITE_DB_PATH": "~/.airautomatica/airautomatica.db",
}

lines = text.splitlines()
existing = {}
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        existing[k.strip()] = v.strip()

for k, v in defaults.items():
    existing[k] = v

# preserve comments and unknown lines poorly? keep it simple and deterministic
new_lines = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in existing and k not in seen:
            new_lines.append(f"{k}={existing[k]}")
            seen.add(k)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

for k, v in existing.items():
    if k not in seen:
        new_lines.append(f"{k}={v}")

env_path.write_text("\n".join(new_lines) + "\n")
PY
fi

echo
echo "==> Setup complete."
echo
echo "Project directory:"
echo "  $APP_DIR"
echo
echo "To run (default: ollama; set LOCAL_LLM_PROVIDER=mock for no-setup testing):"
echo "  cd $APP_DIR"
echo "  source .venv/bin/activate"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  uv run airautomatica"
echo
echo "Then open:"
echo "  http://$(hostname).local:8000/dashboard"
echo "  or"
echo "  http://<pi-ip>:8000/dashboard"
echo
echo "For serial mode later, update .env or export:"
echo "  TELEMETRY_BACKEND=serial"
echo "  SERIAL_PORT=/dev/ttyUSB0   # default; use /dev/ttyACM0 for native USB"
echo "  SERIAL_BAUD=921600"
echo
echo "Helpful checks:"
echo "  ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true"
echo "  dmesg | tail -50"
echo
echo "Note: reboot once so dialout/tty group changes take effect."
