#!/bin/sh
# Optional: Install hailo-apps for real structured object detection.
# Run after install-ai-hat-deps.sh on Pi with AI HAT hardware.
# Requires: hailo-apps cloned (git clone https://github.com/hailo-ai/hailo-apps.git)
#
# Usage:
#   HAILO_APPS_PATH=~/hailo-apps ./install-ai-hat-apps.sh
#   # or from packaging/linux:
#   HAILO_APPS_PATH=~/hailo-apps ./packaging/linux/install-ai-hat-apps.sh
#
# See docs/ai_hat.md
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Path to cloned hailo-apps repo (default: ~/hailo-apps)
HAILO_APPS_PATH="${HAILO_APPS_PATH:-$HOME/hailo-apps}"

# Resolve home for sudo case
if [ -n "${SUDO_USER:-}" ]; then
  SUDO_HOME="$(eval echo "~$SUDO_USER")"
  HAILO_APPS_PATH="${HAILO_APPS_PATH:-$SUDO_HOME/hailo-apps}"
fi

echo "Installing hailo-apps for structured object detection..."
echo "  hailo-apps path: $HAILO_APPS_PATH"

if [ ! -d "$HAILO_APPS_PATH" ]; then
  echo "ERROR: hailo-apps not found at $HAILO_APPS_PATH"
  echo "Clone it first: git clone https://github.com/hailo-ai/hailo-apps.git $HAILO_APPS_PATH"
  exit 1
fi

if [ ! -f "$HAILO_APPS_PATH/setup.py" ] && [ ! -f "$HAILO_APPS_PATH/pyproject.toml" ]; then
  echo "ERROR: $HAILO_APPS_PATH does not look like hailo-apps (no setup.py or pyproject.toml)"
  exit 1
fi

# Prefer packaged venv; else repo venv
if [ -x "/opt/airautomatica/venv/bin/pip" ]; then
  PIP="/opt/airautomatica/venv/bin/pip"
  echo "  Using venv: /opt/airautomatica/venv"
elif [ -x "$REPO_ROOT/.venv/bin/pip" ]; then
  PIP="$REPO_ROOT/.venv/bin/pip"
  echo "  Using venv: $REPO_ROOT/.venv"
elif [ -x "$REPO_ROOT/packaging/linux/.venv/bin/pip" ]; then
  PIP="$REPO_ROOT/packaging/linux/.venv/bin/pip"
  echo "  Using venv: $REPO_ROOT/packaging/linux/.venv"
else
  echo "ERROR: No AirAutomatica venv found."
  echo "  Run packaging/linux/install.sh first (creates /opt/airautomatica/venv)"
  echo "  Or create a venv: cd $REPO_ROOT && python3 -m venv .venv --system-site-packages"
  exit 1
fi

# Install hailo-apps in editable mode (avoids PEP 668; uses venv's pip)
"$PIP" install -e "$HAILO_APPS_PATH"

# Post-install: download models and compile postprocess libs (if hailo-post-install exists in venv)
# Use UTF-8 to avoid UnicodeEncodeError when hailo-post-install prints emoji (hailo-apps bug)
VENV_BIN="$(dirname "$PIP")"
if [ -x "$VENV_BIN/hailo-post-install" ]; then
  echo "Running hailo-post-install..."
  LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}" "$VENV_BIN/hailo-post-install" --group detection 2>/dev/null || true
fi

echo "hailo-apps installed. For one-shot detection, ensure AI_HAT_ENABLED=1 and use POST /api/ai/detect."
