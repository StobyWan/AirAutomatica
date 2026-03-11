#!/usr/bin/env bash
set -euo pipefail

# Download the latest .deb from a GitHub Release.
# Usage: download_latest_deb.sh
#   REPO=owner/repo  override repo (default: StobyWan/AirAutomatica)
#   TAG=v0.1.3       optional: specific tag; omit for latest release

REPO="${REPO:-StobyWan/AirAutomatica}"
TAG="${TAG:-}"

if [[ -n "$TAG" ]]; then
  API_URL="https://api.github.com/repos/${REPO}/releases/tags/${TAG}"
  echo "==> Fetching release: $TAG"
else
  API_URL="https://api.github.com/repos/${REPO}/releases/latest"
  echo "==> Fetching latest release..."
fi

RESPONSE=$(curl -sfL "$API_URL") || {
  echo "Error: failed to fetch release from GitHub."
  echo "Check REPO ($REPO) and TAG ($TAG), or run with TAG=vX.Y.Z for a specific version."
  exit 1
}

URL=$(echo "$RESPONSE" | grep browser_download_url | grep '\.deb"' | head -n 1 | cut -d '"' -f 4)

if [[ -z "$URL" ]]; then
  echo "Error: no .deb asset found in release."
  exit 1
fi

FILENAME="${URL##*/}"
echo "==> Downloading: $FILENAME"

curl -sfL -o "$FILENAME" "$URL"

echo "==> Saved: $FILENAME"
echo "$FILENAME"
