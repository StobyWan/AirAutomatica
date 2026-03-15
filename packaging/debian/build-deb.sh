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

# Build frontend (SPA dashboard)
if command -v npm >/dev/null 2>&1; then
  echo "==> Building frontend"
  (cd "$REPO_ROOT/frontend" && npm ci && VITE_BASE_PATH=/dashboard npm run build)
  if [[ -d "$REPO_ROOT/frontend/dist" ]]; then
    mkdir -p "$OPT_DIR/frontend"
    cp -r "$REPO_ROOT/frontend/dist" "$OPT_DIR/frontend/"
    echo "==> Frontend dist included in package"
    rm -rf "$REPO_ROOT/frontend/node_modules"
    echo "==> Removed node_modules to free disk space"
  else
    echo "WARNING: frontend/dist not found after build; SPA will not be available in .deb"
  fi
else
  echo "WARNING: npm not found; skipping frontend build. SPA will not be available in .deb"
fi

# Build wheel
echo "==> Building wheel"
mkdir -p "$BUILD_DIR/wheels"
python3 -m pip wheel --wheel-dir "$BUILD_DIR/wheels" "$REPO_ROOT"

# Package wheel (venv created on target during postinst)
mkdir -p "$OPT_DIR/wheels"
cp "$BUILD_DIR/wheels"/airautomatica-*.whl "$OPT_DIR/wheels/"

# Copy systemd unit and env example
cp "$LINUX_DIR/airautomatica.service" "$ETC_SYSTEMD/"
cp "$LINUX_DIR/airautomatica.env.example" "$OPT_DIR/"

# Copy alembic for migrations (run at app startup)
cp "$REPO_ROOT/alembic.ini" "$OPT_DIR/"
[[ -d "$REPO_ROOT/alembic" ]] && cp -r "$REPO_ROOT/alembic" "$OPT_DIR/"

# Verify staging contains Alembic assets (catches packaging issues before dpkg)
if [[ ! -f "$OPT_DIR/alembic.ini" ]] || [[ ! -d "$OPT_DIR/alembic/versions" ]]; then
  echo "ERROR: Staging missing alembic.ini or alembic/versions/. Build failed."
  exit 1
fi

# DEBIAN directory
mkdir -p "$STAGING/DEBIAN"
sed "s/^Version: .*/Version: $VERSION/" "$SCRIPT_DIR/control" > "$STAGING/DEBIAN/control"
cp "$SCRIPT_DIR/postinst" "$STAGING/DEBIAN/"
cp "$SCRIPT_DIR/prerm" "$STAGING/DEBIAN/"
cp "$SCRIPT_DIR/postrm" "$STAGING/DEBIAN/"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm" "$STAGING/DEBIAN/postrm"

# Build .deb
echo "==> Building .deb"
DEB_PATH="$REPO_ROOT/airautomatica_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGING" "$DEB_PATH"

# Verify .deb contains Alembic assets
echo "==> Verifying .deb contains Alembic assets"
if ! dpkg -c "$DEB_PATH" | grep -qE "alembic\.ini|alembic/"; then
  echo "ERROR: .deb is missing alembic.ini or alembic/. Build failed."
  exit 1
fi

echo "==> Done: $DEB_PATH"
