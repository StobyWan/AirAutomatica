#!/usr/bin/env bash
# Uninstall AirAutomatica systemd service.
# Run: sudo packaging/linux/uninstall.sh [--purge]
# --purge: also remove /opt/airautomatica, /var/lib/airautomatica, /etc/airautomatica, and user
set -euo pipefail

APP_USER="airautomatica"
OPT_DIR="/opt/airautomatica"
VAR_DIR="/var/lib/airautomatica"
ETC_DIR="/etc/airautomatica"
SERVICE_NAME="airautomatica"

PURGE=false
for arg in "$@"; do
  if [[ "$arg" == "--purge" ]]; then
    PURGE=true
    break
  fi
done

if [[ $(id -u) -ne 0 ]]; then
  echo "ERROR: This script must be run as root (e.g. sudo $0)"
  exit 1
fi

echo "==> Stopping and disabling $SERVICE_NAME"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

echo "==> Removing systemd unit"
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

if [[ "$PURGE" == true ]]; then
  echo "==> Purging install (--purge)"
  rm -rf "$OPT_DIR"
  rm -rf "$VAR_DIR"
  rm -rf "$ETC_DIR"
  if getent passwd "$APP_USER" >/dev/null 2>&1; then
    userdel "$APP_USER" 2>/dev/null || true
  fi
  echo "==> Purge complete."
else
  echo "==> Uninstall complete. Data preserved in $VAR_DIR and $ETC_DIR."
  echo "    To remove everything, run: sudo $0 --purge"
fi
