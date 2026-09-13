#!/usr/bin/env bash
set -e

echo "═════════════════════════════════════════════════════════════"
echo "  Building HotChords v0.4.0 Standalone macOS DMG Installer  "
echo "═════════════════════════════════════════════════════════════"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
APP_NAME="HotChords"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_STAGING="${DIST_DIR}/dmg_staging"
DMG_OUTPUT="${DIST_DIR}/HotChords-v0.4.0-macOS-AppleSilicon.dmg"

# 1. Clean previous build staging
echo "  🧹 Cleaning previous build staging..."
rm -rf "${APP_BUNDLE}" "${DMG_STAGING}" "${DMG_OUTPUT}" "${PROJECT_ROOT}/build"
mkdir -p "${DMG_STAGING}"

cd "${PROJECT_ROOT}"

# 2. Determine Python interpreter for build machine execution
PYTHON_BIN="python3"
if [ -f "${PROJECT_ROOT}/venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python3"
fi

# 3. Bundle standalone application with PyInstaller
echo "  📦 Bundling self-contained standalone application with PyInstaller..."
"${PYTHON_BIN}" -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --name "${APP_NAME}" \
    --osx-bundle-identifier "com.hotfix.hotchords" \
    --add-data "frontend:frontend" \
    --add-data "test songs:test songs" \
    --hidden-import "uvicorn.logging" \
    --hidden-import "uvicorn.loops" \
    --hidden-import "uvicorn.loops.auto" \
    --hidden-import "uvicorn.protocols" \
    --hidden-import "uvicorn.protocols.http" \
    --hidden-import "uvicorn.protocols.http.auto" \
    --hidden-import "uvicorn.lifespan" \
    --hidden-import "uvicorn.lifespan.on" \
    --hidden-import "soundfile" \
    --hidden-import "imageio_ffmpeg" \
    --hidden-import "scipy.special.cython_special" \
    --collect-all "librosa" \
    --collect-all "imageio_ffmpeg" \
    "hotchords.py"

if [ ! -d "${APP_BUNDLE}" ]; then
    echo "❌ Error: PyInstaller failed to produce ${APP_BUNDLE}"
    exit 1
fi

# 4. Finalize Info.plist metadata and bundle resources
echo "  ⚙️ Customizing Info.plist..."
cat << 'EOF' > "${APP_BUNDLE}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>HotChords</string>
    <key>CFBundleIdentifier</key>
    <string>com.hotfix.hotchords</string>
    <key>CFBundleName</key>
    <string>HotChords</string>
    <key>CFBundleDisplayName</key>
    <string>HotChords</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.4.0</string>
    <key>CFBundleVersion</key>
    <string>0.4.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# 5. Code sign final application bundle (Ad-hoc signature)
echo "  🔏 Code signing finalized application bundle..."
codesign --force --deep -s - "${APP_BUNDLE}"

# 6. Verify signature integrity
echo "  🔍 Verifying code signature integrity..."
codesign --verify --deep --strict --verbose=2 "${APP_BUNDLE}"

# 7. Assessment with spctl
echo "  🛡️ Checking Gatekeeper assessment..."
spctl --assess --type execute --verbose=2 "${APP_BUNDLE}" || true

# 8. Create compressed DMG
echo "  💿 Preparing DMG staging layout..."
cp -R "${APP_BUNDLE}" "${DMG_STAGING}/"
ln -s /Applications "${DMG_STAGING}/Applications"

echo "  🔨 Creating UDZO compressed DMG disk image..."
hdiutil create -volname "HotChords" -srcfolder "${DMG_STAGING}" -ov -format UDZO "${DMG_OUTPUT}"

rm -rf "${DMG_STAGING}"

echo ""
echo "═════════════════════════════════════════════════════════════"
echo "  ✅ Standalone macOS DMG Installer Successfully Built at:"
echo "     ${DMG_OUTPUT}"
echo "═════════════════════════════════════════════════════════════"
