#!/usr/bin/env bash
# Build tracker.app and wrap it in a .dmg for macOS.
# Intended to run on a macOS GitHub Actions runner (macos-15-intel) or a Mac.
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
mkdir -p "$BUILD_DIR" "$DIST_DIR"

echo "==> Making app icon (.icns)"
ICONSET="$BUILD_DIR/icon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" "$ROOT/scripts/icons/tracker-512.png" \
    --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  s2=$((s * 2))
  sips -z "$s2" "$s2" "$ROOT/scripts/icons/tracker-512.png" \
    --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BUILD_DIR/tracker.icns"

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --specpath "$BUILD_DIR" \
  --add-data "$ROOT/sample.json:." \
  --add-data "$ROOT/scripts/icons/tracker-512.png:." \
  --icon "$BUILD_DIR/tracker.icns" \
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
