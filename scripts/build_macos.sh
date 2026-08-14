#!/usr/bin/env bash
# Build tracker.app and wrap it in a .dmg for macOS.
# Intended to run on a macOS GitHub Actions runner (macos-13) or a Mac.
set -euo pipefail

APP_NAME="tracker"
VERSION="${1:-1.0.0}"
PYTHON="python3"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT/build"
DIST_DIR="$ROOT/dist"

echo "==> Building $APP_NAME-$VERSION"
cd "$ROOT"

if [ "$(uname)" != "Darwin" ]; then
  echo "ERROR: this script must run on macOS." >&2
  exit 1
fi

export MACOSX_DEPLOYMENT_TARGET=12.0

echo "==> Installing PyInstaller"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install pyinstaller

echo "==> Bundling .app"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$DIST_DIR"
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --specpath "$BUILD_DIR" \
  --add-data "sample.json:." \
  "$ROOT/run.py"

APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
echo "==> Created $APP_BUNDLE"

echo "==> Creating DMG"
STAGE="$BUILD_DIR/dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP_BUNDLE" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

DMG="$DIST_DIR/${APP_NAME}-${VERSION}-macos.dmg"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG"

echo "==> Done: $DMG"
ls -lh "$DMG"
