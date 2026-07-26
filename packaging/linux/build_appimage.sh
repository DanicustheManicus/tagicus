#!/bin/bash
# Builds Tagicus-x86_64.AppImage from the PyInstaller onefile executable.
# Run tagicus.spec first so dist/Tagicus exists.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_EXE="$PROJECT_ROOT/dist/Tagicus"
APPDIR="$PROJECT_ROOT/build/AppDir"
APPIMAGETOOL="$PROJECT_ROOT/build/appimagetool-x86_64.AppImage"
OUT="$PROJECT_ROOT/dist/Tagicus-x86_64.AppImage"

if [ ! -f "$DIST_EXE" ]; then
    echo "error: $DIST_EXE not found - run 'pyinstaller tagicus.spec' first" >&2
    exit 1
fi

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "$DIST_EXE" "$APPDIR/usr/bin/Tagicus"
cp "$PROJECT_ROOT/packaging/linux/tagicus.desktop" "$APPDIR/tagicus.desktop"
cp "$PROJECT_ROOT/packaging/linux/tagicus.desktop" "$APPDIR/usr/share/applications/tagicus.desktop"
cp "$PROJECT_ROOT/assets/icon.png" "$APPDIR/tagicus.png"
cp "$PROJECT_ROOT/assets/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/tagicus.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/Tagicus" "$@"
EOF
chmod +x "$APPDIR/AppRun"

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    curl -sL -o "$APPIMAGETOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$APPIMAGETOOL"
fi

rm -f "$OUT"
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT"
echo "Built $OUT"
