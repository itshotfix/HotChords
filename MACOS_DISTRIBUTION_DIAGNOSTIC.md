# HotChords — macOS Installation & Gatekeeper Diagnostic Report

**Diagnostic Date**: 2026-09-13  
**Status**: NOT READY — MACOS DISTRIBUTION BLOCKER  
**Investigation Scope**: Static & runtime inspection using `codesign`, `spctl`, `security`, and `xattr` (Zero code changes / no rebuilds performed in this phase).

---

## 1. Status Matrix

```text
MACOS_DMGBUILD = PASS
APP_BUNDLE = PASS
PYTHON_RUNTIME = PASS
APP_EXECUTION = PASS
CODE_SIGNATURE = FAIL
GATEKEEPER = FAIL
NORMAL_INSTALL_FLOW = FAIL
DEVELOPER_ID = NO
NOTARIZED = NO
STAPLED = NO
```

---

## 2. Exact Root Cause Analysis

### Diagnostic Evidence
Running `codesign --verify --deep --strict --verbose=4 dist/HotChords.app` produced:
```text
/Volumes/TIKDI/APP Development/HotChords App/dist/HotChords.app: invalid Info.plist (plist or signature have been modified)
In architecture: arm64
```

### Why Normal Installation / Gatekeeper Failed
1. **Post-Signing File Mutation Bug in `scripts/build_macos_dmg.sh`**:
   - PyInstaller compiled `HotChords.app` and sealed all files in `_CodeSignature/CodeResources` with an ad-hoc signature.
   - Immediately following the PyInstaller step, `scripts/build_macos_dmg.sh` executed:
     ```bash
     cat << 'EOF' > "${APP_BUNDLE}/Contents/Info.plist"
     ...
     EOF
     ```
   - This modified `Contents/Info.plist` on disk **after** the signature was generated.
2. **Broken Resource Seal**:
   - The SHA-256 hash of `Info.plist` recorded in `Contents/_CodeSignature/CodeResources` no longer matched the actual file on disk.
3. **macOS System Verification Abort**:
   - When Finder or Gatekeeper verifies an app bundle before installation or launch, it verifies the cryptographic seal of `Info.plist`.
   - Because the hash mismatched, macOS flagged the bundle as damaged/tampered and aborted the installation with:
     > *"Could not install. This Mac could not verify the app, so nothing was installed."*

---

## 3. Credential & Distribution Model Audit

### Keychain Audit Result
Running `security find-identity -v -p codesigning` returned:
```text
0 valid identities found
```

### Summary of Distribution Realities:
- **`NOTARIZATION_CREDENTIALS_AVAILABLE = NO`**:
  - No Apple Developer ID Application certificate or App Store Connect API keys exist in the current development environment.
  - Official Apple Notarization (`xcrun notarytool`) and Stapling (`xcrun stapler`) cannot be performed without an active Apple Developer account.
- **Comparison of Options**:
  - **Option A (Developer ID + Notarization + Stapling)**: The only way to achieve seamless double-click launch with zero Gatekeeper prompts on web downloads. Requires Apple Developer Program credentials.
  - **Option B (Clean Ad-Hoc Signing without Notarization)**: Fixing the signature seal (`codesign --force --deep -s -`) ensures the bundle is valid and untampered on disk. It will allow local installation, but web downloads with quarantine attributes will require the standard macOS open flow (Right-Click -> Open or System Settings -> "Open Anyway").
  - **Option C (Broken Signature - Current State)**: The app is rejected outright with fatal verification errors even before reaching the standard override options.

---

## 4. Required Fix Plan

### Step 1: Fix `build_macos_dmg.sh` Build Order & Re-signing
1. Either supply the custom `Info.plist` to PyInstaller during the build phase (or write it before PyInstaller signs), OR
2. Explicitly re-sign the entire bundle with deep sealed resources after writing `Info.plist`:
   ```bash
   codesign --force --deep -s - "${APP_BUNDLE}"
   ```
3. Verify signature validity immediately during build:
   ```bash
   codesign --verify --deep --strict "${APP_BUNDLE}"
   ```

### Step 2: Document Gatekeeper Guidance for Open-Source Users
Because Developer ID credentials are not present (`NOTARIZATION_CREDENTIALS_AVAILABLE = NO`), document the standard open-source macOS first-launch step in `README.md` and release notes:
- *First Launch*: Right-click `HotChords.app` in `/Applications` -> Select **Open** -> Click **Open**.

---

## 5. Overall Release Status

```text
OVERALL STATUS: NOT READY — MACOS DISTRIBUTION BLOCKER
```
The macOS installer cannot be declared release-ready until the code signature seal is intact and verified with `codesign --verify --deep --strict`.
