#!/bin/sh
# Optional: Install Hailo packages for Raspberry Pi AI HAT+ (Hailo-8L).
# Run manually on Pi with AI HAT hardware. See docs/ai_hat.md
set -e

echo "Installing Hailo packages for Raspberry Pi AI HAT+ (Hailo-8L)..."

apt-get update
apt-get install -y \
  hailo-all \
  hailo-models \
  hailo-tappas-core \
  hailort \
  hailort-pcie-driver \
  python3-hailort \
  python3-hailo-tappas \
  rpicam-apps-hailo-postprocess

echo "Hailo packages installed. Verify with: dpkg -l | grep hailo"
echo "Test camera + Hailo: rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov6_inference.json"
