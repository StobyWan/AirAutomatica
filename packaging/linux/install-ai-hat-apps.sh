#!/bin/sh
# Optional: Install hailo-apps for real structured object detection.
# Run after install-ai-hat-deps.sh on Pi with AI HAT hardware.
# See docs/ai_hat.md
set -e

echo "Installing hailo-apps for structured object detection..."

if ! command -v pip3 >/dev/null 2>&1; then
  echo "pip3 not found. Install Python and pip first."
  exit 1
fi

# pip install (use --user to avoid system-wide install)
pip3 install --user hailo-apps || pip3 install hailo-apps

# Post-install: download models and compile postprocess libs
if command -v hailo-post-install >/dev/null 2>&1; then
  echo "Running hailo-post-install..."
  hailo-post-install --group detection 2>/dev/null || true
fi

echo "hailo-apps installed. For one-shot detection, ensure AI_HAT_ENABLED=1 and use POST /api/ai/detect."
