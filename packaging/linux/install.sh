#!/usr/bin/env bash
# Install AirAutomatica as a systemd-managed service.
# Run from repo root: sudo packaging/linux/install.sh
# Requires: root, python3, pip, venv
set -euo pipefail

APP_USER="airautomatica"
OPT_DIR="/opt/airautomatica"
VAR_DIR="/var/lib/airautomatica"
ETC_DIR="/etc/airautomatica"
SERVICE_NAME="airautomatica"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: This script must be run as root (e.g. sudo $0)"
  exit 1
fi

echo "==> Installing AirAutomatica from $REPO_ROOT"

# 1. Create system user if missing
if ! getent passwd "$APP_USER" >/dev/null 2>&1; then
  echo "==> Creating system user $APP_USER"
  useradd --system --home "$VAR_DIR" --shell /usr/sbin/nologin "$APP_USER"
else
  echo "==> User $APP_USER already exists"
fi

# 2. Create directories
echo "==> Creating directories"
mkdir -p "$OPT_DIR" "$VAR_DIR" "$ETC_DIR"

# 3. Copy app files
echo "==> Copying app files to $OPT_DIR"
cp -r "$REPO_ROOT/src" "$OPT_DIR/"
cp "$REPO_ROOT/pyproject.toml" "$OPT_DIR/"
cp "$REPO_ROOT/README.md" "$OPT_DIR/" 2>/dev/null || true
[[ -d "$REPO_ROOT/alembic" ]] && cp -r "$REPO_ROOT/alembic" "$OPT_DIR/"
[[ -f "$REPO_ROOT/alembic.ini" ]] && cp "$REPO_ROOT/alembic.ini" "$OPT_DIR/" 2>/dev/null || true

# 4. Create venv and install
echo "==> Creating virtual environment and installing dependencies"
if [[ -d "$OPT_DIR/venv" ]]; then
  rm -rf "$OPT_DIR/venv"
fi
python3 -m venv "$OPT_DIR/venv"
"$OPT_DIR/venv/bin/pip" install --upgrade pip
"$OPT_DIR/venv/bin/pip" install -e "$OPT_DIR"

# 5. Install env template only if not present
ENV_FILE="$ETC_DIR/airautomatica.env"
ENV_EXAMPLE="$SCRIPT_DIR/airautomatica.env.example"
if [[ ! -f "$ENV_FILE" ]] && [[ -f "$ENV_EXAMPLE" ]]; then
  echo "==> Installing env template to $ENV_FILE"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
else
  echo "==> Env file already exists, skipping template"
fi

# 6. Add dialout for serial access (no-op if already in group)
usermod -aG dialout "$APP_USER" 2>/dev/null || true

# 7. Set ownership
echo "==> Setting ownership"
chown -R "$APP_USER:$APP_USER" "$OPT_DIR" "$VAR_DIR"

# 8. Install systemd unit
echo "==> Installing systemd unit"
cp "$SCRIPT_DIR/airautomatica.service" /etc/systemd/system/

# 9. Reload and enable
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "==> Installation complete."
echo ""
echo "Next steps:"
echo "  1. Edit config if needed: sudo nano $ENV_FILE"
echo "  2. Start the service:      sudo systemctl start $SERVICE_NAME"
echo "  3. Check status:           sudo systemctl status $SERVICE_NAME"
echo "  4. View logs:              journalctl -u $SERVICE_NAME -f"
echo ""
echo "Default: mock mode (no FC, serial, or Ollama required)."
echo "To switch to real hardware, edit $ENV_FILE and restart."
echo ""
