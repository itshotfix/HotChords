#!/usr/bin/env bash
set -e

echo "═════════════════════════════════════════════════════════════"
echo "  Building HotChords v0.3.0 Standalone macOS DMG Installer  "
echo "═════════════════════════════════════════════════════════════"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
APP_NAME="HotChords"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_STAGING="${DIST_DIR}/dmg_staging"
DMG_OUTPUT="${DIST_DIR}/HotChords-v0.3.0-macOS-AppleSilicon.dmg"

rm -rf "${APP_BUNDLE}" "${DMG_STAGING}" "${DMG_OUTPUT}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"
mkdir -p "${DMG_STAGING}"

echo "  📦 Copying application source and assets..."
cp -R "${PROJECT_ROOT}/backend" "${APP_BUNDLE}/Contents/Resources/"
cp -R "${PROJECT_ROOT}/frontend" "${APP_BUNDLE}/Contents/Resources/"
cp -R "${PROJECT_ROOT}/test songs" "${APP_BUNDLE}/Contents/Resources/"
cp "${PROJECT_ROOT}/hotchords.py" "${APP_BUNDLE}/Contents/Resources/"
cp "${PROJECT_ROOT}/requirements.txt" "${APP_BUNDLE}/Contents/Resources/"

echo "  ⚙️ Creating Info.plist..."
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
    <string>0.3.0</string>
    <key>CFBundleVersion</key>
    <string>0.3.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "  🚀 Creating launcher executable..."
cat << 'EOF' > "${APP_BUNDLE}/Contents/MacOS/HotChords"
#!/usr/bin/env bash
RESOURCE_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "${RESOURCE_DIR}"

# Find Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif [ -f "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -f "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
else
    PYTHON_BIN="python"
fi

exec "${PYTHON_BIN}" hotchords.py
EOF

chmod +x "${APP_BUNDLE}/Contents/MacOS/HotChords"

echo "  💿 Preparing DMG staging layout..."
cp -R "${APP_BUNDLE}" "${DMG_STAGING}/"
ln -s /Applications "${DMG_STAGING}/Applications"

echo "  🔨 Creating UDZO compressed DMG disk image..."
hdiutil create -volname "HotChords" -srcfolder "${DMG_STAGING}" -ov -format UDZO "${DMG_OUTPUT}"

rm -rf "${DMG_STAGING}"

echo ""
echo "═════════════════════════════════════════════════════════════"
echo "  ✅ macOS DMG Installer Successfully Built at:"
echo "     ${DMG_OUTPUT}"
echo "═════════════════════════════════════════════════════════════"
