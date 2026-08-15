#!/usr/bin/env bash
# Build tracker for Linux: a .deb (Debian/Ubuntu) and a portable AppImage.
# Works on x86_64 and aarch64. Run on the same architecture as the target.
set -euo pipefail

APP_NAME="tracker"
VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT/build"
DIST_DIR="$ROOT/dist"
ICONS="$ROOT/scripts/icons"

MACHINE="$(uname -m)"
case "$MACHINE" in
  x86_64)  DEB_ARCH="amd64"; APPIMAGE_ARCH="x86_64";;
  aarch64) DEB_ARCH="arm64";  APPIMAGE_ARCH="aarch64";;
  *)
    echo "ERROR: unsupported machine $MACHINE (expected x86_64 or aarch64)." >&2
    exit 1;;
esac

echo "==> Building $APP_NAME-$VERSION for $DEB_ARCH"
cd "$ROOT"

echo "==> Installing PyInstaller"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR"
VENV="$BUILD_DIR/.pybuild-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q pyinstaller

echo "==> Bundling with PyInstaller"
rm -rf "$DIST_DIR"
"$VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --specpath "$BUILD_DIR" \
  --add-data "$ROOT/sample.json:." \
  "$ROOT/run.py"

BUNDLE="$DIST_DIR/$APP_NAME"

# ---------------------------------------------------------------- .deb ----
DEB="$DIST_DIR/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb"
STAGE="$BUILD_DIR/deb/${APP_NAME}_${VERSION}_${DEB_ARCH}"
echo "==> Building .deb: $DEB"

mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/lib/$APP_NAME" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor" \
         "$STAGE/usr/share/metainfo"

cp -r "$BUNDLE"/. "$STAGE/usr/lib/$APP_NAME/"

cat > "$STAGE/usr/bin/$APP_NAME" <<EOF
#!/bin/sh
exec /usr/lib/$APP_NAME/$APP_NAME "\$@"
EOF
chmod +x "$STAGE/usr/bin/$APP_NAME"

cat > "$STAGE/usr/share/applications/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Tournament Tracker
Comment=Chess tournaments near you (FIDE & non-FIDE)
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=Game;BoardGame;
StartupNotify=false
EOF

cp "$ROOT/packaging/tracker.metainfo.xml" "$STAGE/usr/share/metainfo/"

for size in 16 32 48 64 128 256; do
  install -D "$ICONS/tracker-$size.png" \
    "$STAGE/usr/share/icons/hicolor/${size}x${size}/apps/$APP_NAME.png"
done

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $APP_NAME
Version: $VERSION
Section: games
Priority: optional
Architecture: $DEB_ARCH
Maintainer: Tournament Tracker <noreply@localhost>
Depends: libx11-6, libxft2, libfontconfig1, tk
Description: Chess tournament tracker
 Desktop app that lists upcoming FIDE and non-FIDE chess tournaments near
 Bengaluru, served as JSON from a Raspberry Pi.
EOF

dpkg-deb --build --root-owner-group "$STAGE" "$DEB"

# ------------------------------------------------------------ AppImage ----
APPIMAGE="$DIST_DIR/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
TOOL="$BUILD_DIR/appimagetool"
echo "==> Building AppImage: $APPIMAGE"

if [ ! -x "$TOOL" ]; then
  echo "--> Downloading appimagetool for $APPIMAGE_ARCH"
  curl -sL "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage" -o "$TOOL"
  chmod +x "$TOOL"
fi

APPDIR="$BUILD_DIR/appdir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo"

cp -r "$BUNDLE"/. "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
SELF="\$(readlink -f "\$0")"
HERE="\${SELF%/*}"
exec "\$HERE/usr/bin/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Tournament Tracker
Comment=Chess tournaments near you (FIDE & non-FIDE)
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=Game;BoardGame;
StartupNotify=false
EOF
cp "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/tracker.metainfo.xml" "$APPDIR/usr/share/metainfo/"

cp "$ICONS/tracker-256.png" "$APPDIR/$APP_NAME.png"
cp "$ICONS/tracker-256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

export ARCH="$APPIMAGE_ARCH"
"$TOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE"

echo
echo "==> Done:"
ls -lh "$DEB" "$APPIMAGE"
