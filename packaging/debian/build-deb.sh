#!/usr/bin/env bash
# Build a .deb package for AirAutomatica.
# Run from repo root: ./packaging/debian/build-deb.sh
# Optional: VERSION=0.1.0 ./packaging/debian/build-deb.sh
# Output: airautomatica_<version>_all.deb in repo root
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LINUX_DIR="$(cd "$SCRIPT_DIR/../linux" && pwd)"

# Version from env, or git tag, or pyproject.toml
if [[ -n "${VERSION:-}" ]]; then
  VERSION="$VERSION"
elif git describe --tags --match 'v*' --abbrev=0 2>/dev/null; then
  VERSION="$(git describe --tags --match 'v*' --abbrev=0 | sed 's/^v//')"
else
  VERSION="$(grep -E '^version\s*=' "$REPO_ROOT/pyproject.toml" | sed 's/.*=\s*"\(.*\)"/\1/')"
fi

BUILD_DIR="$REPO_ROOT/build/deb"
STAGING="$BUILD_DIR/airautomatica_${VERSION}"
OPT_DIR="$STAGING/opt/airautomatica"
ETC_SYSTEMD="$STAGING/etc/systemd/system"

echo "==> Building airautomatica_${VERSION}_all.deb"

# Clean staging
rm -rf "$STAGING"
mkdir -p "$OPT_DIR" "$ETC_SYSTEMD"

# Build wheel
echo "==> Building wheel"
mkdir -p "$BUILD_DIR/wheels"
python3 -m pip wheel --wheel-dir "$BUILD_DIR/wheels" "$REPO_ROOT"

# Create venv and install
echo "==> Creating venv and installing"
python3 -m venv "$OPT_DIR/venv"
"$OPT_DIR/venv/bin/pip" install --upgrade pip
"$OPT_DIR/venv/bin/pip" install "$BUILD_DIR/wheels"/airautomatica-*.whl

# Copy systemd unit and env example
cp "$LINUX_DIR/airautomatica.service" "$ETC_SYSTEMD/"
cp "$LINUX_DIR/airautomatica.env.example" "$OPT_DIR/"

# DEBIAN directory
mkdir -p "$STAGING/DEBIAN"
sed "s/^Version: .*/Version: $VERSION/" "$SCRIPT_DIR/control" > "$STAGING/DEBIAN/control"
cp "$SCRIPT_DIR/postinst" "$STAGING/DEBIAN/"
cp "$SCRIPT_DIR/prerm" "$STAGING/DEBIAN/"
cp "$SCRIPT_DIR/postrm" "$STAGING/DEBIAN/"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm" "$STAGING/DEBIAN/postrm"

# Build .deb
echo "==> Building .deb"
dpkg-deb --root-owner-group --build "$STAGING" "$REPO_ROOT/airautomatica_${VERSION}_all.deb"

echo "==> Done: $REPO_ROOT/airautomatica_${VERSION}_all.deb"
