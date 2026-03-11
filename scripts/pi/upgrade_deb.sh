#!/usr/bin/env bash
set -euo pipefail

# Upgrade AirAutomatica from a .deb package.
# Usage: upgrade_deb.sh [path-to-deb]
#   With arg: use the given .deb file.
#   Without arg: infer from latest git tag (e.g. v0.1.3 -> airautomatica_0.1.3_all.deb).

DEB="${1:-}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"

if [[ -z "$DEB" ]]; then
  echo "==> No .deb path provided; inferring from latest git tag..."
  if ! command -v git &>/dev/null; then
    echo "Error: git not found. Pass the .deb file explicitly: upgrade_deb.sh <path-to-deb>"
    exit 1
  fi
  if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Error: not a git repository. Pass the .deb file explicitly: upgrade_deb.sh <path-to-deb>"
    exit 1
  fi
  TAG=$(git tag --sort=-version:refname 2>/dev/null | head -n 1)
  if [[ -z "$TAG" ]]; then
    echo "Error: no git tags found. Pass the .deb file explicitly: upgrade_deb.sh <path-to-deb>"
    exit 1
  fi
  echo "==> Latest tag: $TAG"
  VERSION="${TAG#v}"
  DEB="airautomatica_${VERSION}_all.deb"
  echo "==> Inferred package: $DEB"
  if [[ ! -f "$DEB" ]]; then
    echo "Error: file not found: $DEB"
    echo "Run from the directory containing the .deb, or pass the path explicitly."
    exit 1
  fi
  echo "==> Found: $DEB"
fi

if [[ ! -f "$DEB" ]]; then
  echo "Error: file not found: $DEB"
  exit 1
fi

echo "==> Stopping airautomatica..."
sudo systemctl stop airautomatica 2>/dev/null || true

echo "==> Installing package: $DEB"
if ! sudo dpkg -i "$DEB"; then
  echo ""
  echo "If dpkg failed due to dependencies, run: sudo apt-get install -f"
  exit 1
fi

echo "==> Reloading systemd..."
sudo systemctl daemon-reload

echo "==> Starting airautomatica..."
sudo systemctl start airautomatica

echo "==> Service status:"
sudo systemctl status airautomatica --no-pager

echo "==> Health check:"
curl -sf "$HEALTH_URL"

echo ""
echo "==> Installed version:"
dpkg -l | grep airautomatica || true

echo ""
echo "Upgrade complete. Health check OK."
