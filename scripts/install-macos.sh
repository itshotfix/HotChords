#!/usr/bin/env bash
set -euo pipefail

# Optional one-command installer for HotChords on macOS.
# Primary installation remains downloading the DMG from GitHub Releases and
# dragging HotChords.app into /Applications.

VERSION="${HOTCHORDS_VERSION:-0.5.0}"
EXPECTED_SHA256="${HOTCHORDS_SHA256:-}"
REPO="itshotfix/HotChords"
APP_NAME="HotChords.app"
INSTALL_DIR="/Applications"

echo "HotChords v${VERSION} — Optional macOS Installer"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "Error: This script is only for macOS." >&2
    exit 1
fi

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    ASSET_NAME="HotChords-v${VERSION}-macOS-AppleSilicon.dmg"
elif [ "$ARCH" = "x86_64" ]; then
    echo "Error: Prebuilt macOS Intel binaries are not published for v${VERSION} (Apple Silicon only)." >&2
    echo "You can run HotChords from source using Python 3.10+." >&2
    exit 1
else
    echo "Error: Unsupported macOS architecture: ${ARCH}" >&2
    exit 1
fi

MACOS_VER="$(sw_vers -productVersion)"
MACOS_MAJOR="${MACOS_VER%%.*}"
if [ "$MACOS_MAJOR" -lt 11 ]; then
    echo "Error: HotChords requires macOS 11.0 or newer (detected ${MACOS_VER})." >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
MOUNT_DIR="$(mktemp -d)"
cleanup() {
    hdiutil detach "$MOUNT_DIR" -quiet 2>/dev/null || true
    rm -rf "$TMP_DIR" "$MOUNT_DIR"
}
trap cleanup EXIT

DMG_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${ASSET_NAME}"
SHA_URL="https://github.com/${REPO}/releases/download/v${VERSION}/macos_dmg_sha256.txt"
DMG_PATH="${TMP_DIR}/${ASSET_NAME}"
SHA_PATH="${TMP_DIR}/macos_dmg_sha256.txt"

echo "Downloading ${ASSET_NAME} from official GitHub Releases..."
if ! curl -fsSL --proto '=https' --tlsv1.2 "$DMG_URL" -o "$DMG_PATH"; then
    echo "Error: Could not download ${DMG_URL}." >&2
    echo "Verify that release v${VERSION} is published at https://github.com/${REPO}/releases" >&2
    exit 1
fi

if [ -z "$EXPECTED_SHA256" ]; then
    if curl -fsSL --proto '=https' --tlsv1.2 "$SHA_URL" -o "$SHA_PATH"; then
        EXPECTED_SHA256="$(awk '{print $1}' "$SHA_PATH" | head -n 1)"
    fi
fi

if [ -z "$EXPECTED_SHA256" ]; then
    echo "Error: No SHA-256 checksum available to verify ${ASSET_NAME}. Aborting installation." >&2
    exit 1
fi

ACTUAL_SHA256="$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "Error: SHA-256 checksum mismatch!" >&2
    echo "  Expected: ${EXPECTED_SHA256}" >&2
    echo "  Actual:   ${ACTUAL_SHA256}" >&2
    exit 1
fi
echo "SHA-256 checksum verified: ${ACTUAL_SHA256}"

echo "Mounting ${ASSET_NAME}..."
hdiutil attach "$DMG_PATH" -mountpoint "$MOUNT_DIR" -nobrowse -quiet

SRC_APP="${MOUNT_DIR}/${APP_NAME}"
DEST_APP="${INSTALL_DIR}/${APP_NAME}"

if [ ! -d "$SRC_APP" ]; then
    echo "Error: ${APP_NAME} not found inside mounted DMG." >&2
    exit 1
fi

if [ -d "$DEST_APP" ]; then
    echo "Existing ${DEST_APP} found. Updating application bundle (user data is preserved)..."
fi

if [ -w "$INSTALL_DIR" ]; then
    rm -rf "$DEST_APP"
    cp -R "$SRC_APP" "$DEST_APP"
else
    echo "Administrator permission is required to write to ${INSTALL_DIR}."
    sudo rm -rf "$DEST_APP"
    sudo cp -R "$SRC_APP" "$DEST_APP"
fi

echo ""
echo "HotChords v${VERSION} installed to ${DEST_APP}."
echo "Note: HotChords is ad-hoc signed and not Apple notarized."
echo "On first launch, right-click HotChords.app -> Open (or allow it in System Settings -> Privacy & Security)."
