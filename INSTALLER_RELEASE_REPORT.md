# HotChords Installer Release Report

- **Date:** September 12, 2026
- **Release Version:** `v0.4.0` (`0.4.0`)
- **Auditor:** HotChords Release Engineering Team
- **Status:** Complete / Verified

---

## 1. Release Version

- **Target Version:** `v0.4.0` (`0.4.0`)
- **Version Source:** Authoritative release version established during the Phase 14.3 version audit ([`RELEASE_VERSION_AUDIT.md`](RELEASE_VERSION_AUDIT.md)).
- **Synchronized Across:**
  - `package.json` (`0.4.0`)
  - `backend/models/__init__.py` (`APP_VERSION = "0.4.0"`)
  - `frontend/index.html` (`VER 0.4`)
  - `scripts/build_macos_dmg.sh` (`0.4.0`)
  - `SONG_RESULT_CONTRACT.md` (`0.4.0`)
  - `Info.plist` inside `HotChords.app` (`CFBundleShortVersionString = "0.4.0"`, `CFBundleVersion = "0.4.0"`)

---

## 2. Installer Inventory

| Platform | Installer / Artifact | Build Script | Bundled Version | Architecture | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **macOS** | `HotChords-v0.4.0-macOS-AppleSilicon.dmg` | [`scripts/build_macos_dmg.sh`](scripts/build_macos_dmg.sh) | `0.4.0` | Apple Silicon (M1/M2/M3/M4) / Universal Python | **READY** |
| **macOS (Source / CLI)** | `scripts/setup_mac.sh` + `start_mac.sh` | Shell scripts | `0.4.0` | All macOS | **READY** |
| **Windows (Source / CLI)** | `scripts/setup_windows.bat` + `start_windows.bat` | Batch scripts | `0.4.0` | 64-bit Windows | **READY** |

---

## 3. Installer Build System

The macOS standalone distribution is built via `scripts/build_macos_dmg.sh`:
1. **Clean Staging:** Purges old `dist/HotChords.app`, `dist/dmg_staging`, and previous DMG files to prevent stale packaging.
2. **Bundle Assembly:** Creates standard macOS `.app` bundle structure:
   - `Contents/MacOS/HotChords` (executable bash launcher finding Python 3 runtime)
   - `Contents/Info.plist` (metadata, bundle ID `com.hotfix.hotchords`, version `0.4.0`)
   - `Contents/Resources/` (copies current `backend/`, `frontend/`, `hotchords.py`, `requirements.txt`, bundled piano sampler audio)
3. **DMG Disk Image Generation:** Creates a UDZO zlib-compressed `.dmg` with an `/Applications` drag-and-drop symlink.

---

## 4. Changes Made for Installer Release

- **`scripts/build_macos_dmg.sh`:** Updated output artifact name to `HotChords-v0.4.0-macOS-AppleSilicon.dmg` and synchronized `CFBundleShortVersionString` and `CFBundleVersion` to `0.4.0`.
- **`README.md`:** Updated download table and installation instructions to reflect `v0.4.0`.
- **`RELEASE_CHECKLIST.md`:** Added explicit installer validation criteria.
- **`.gitignore`:** Verified `dist/` is ignored from git tracking while ensuring bundled piano audio assets (`frontend/audio/samples/*.mp3`) are tracked.

---

## 5. Installer Build Execution & Hashes

- **Build Command:** `bash scripts/build_macos_dmg.sh`
- **Build Status:** Exit code `0` (Success)
- **Artifact Path:** `dist/HotChords-v0.4.0-macOS-AppleSilicon.dmg`
- **Artifact Size:** `20 MB` (UDZO compressed disk image)
- **SHA-256 Checksum:**
  ```
  49d8008569c1b88b027149eeb4c5a4fc8804f650a55a2cf4adf338d6d843404f
  ```

---

## 6. Installed Application Verification (Clean-Room Smoke Test)

The built disk image was mounted and audited via `hdiutil attach`:
- **Mount Point:** `/Volumes/HotChords_DMG_Test`
- **Volume Contents:**
  - `Applications -> /Applications` symlink verified
  - `HotChords.app` verified
- **`Info.plist` Inspection:**
  - `CFBundleDisplayName`: `HotChords`
  - `CFBundleIdentifier`: `com.hotfix.hotchords`
  - `CFBundleShortVersionString`: `0.4.0`
  - `CFBundleVersion`: `0.4.0`
  - `LSMinimumSystemVersion`: `11.0`
- **Launcher Execution:** `Contents/MacOS/HotChords` launches `hotchords.py` with the local Python runtime.
- **Resources Verification:** Verified `Contents/Resources/` contains the full `v0.4.0` frontend, backend analysis engines, Salamander Grand Piano audio samples, and REST server router.

---

## 7. Bundle Audit

- **Info.plist:** Present, valid XML format, version `0.4.0`.
- **Executable Launcher:** Present (`Contents/MacOS/HotChords`), permissions `755` executable.
- **Resources Directory:** Complete copy of current repository state.
- **Piano Sampler Assets:** 30 `.mp3` sample files present under `Contents/Resources/frontend/audio/samples/`.
- **Machine Paths:** Zero hardcoded developer-local paths (`/Users/...`, `/Volumes/TIKDI/...`) embedded in packaged runtime source files.

---

## 8. Stale Build Audit: **PASS**
- The build script strictly purges `dist/` before staging.
- File timestamps in `dist/HotChords.app` match the September 12, 2026 build execution.
- No legacy files from `v0.2.0` or `v0.3.0` were packaged.

---

## 9. Security Audit: **PASS**
- No secrets, tokens, API keys, private passwords, or SSH paths are contained in the `.dmg`.
- No sensitive configuration files packaged.

---

## 10. Licensing & Model Distribution Audit: **PASS**
- **MIT License:** Core application codebase ([LICENSE](LICENSE)).
- **CC-BY 3.0:** Salamander Grand Piano samples ([frontend/audio/samples/LICENSE.txt](frontend/audio/samples/LICENSE.txt)).
- **Demucs Pretrained Weights:** Weights are downloaded dynamically by PyTorch/TorchHub to user cache on first stem separation run, avoiding bundling non-redistributable binary weights into the installer.

---

## 11. Documentation Updates

- Updated [README.md](README.md) with `v0.4.0` installer download guidance.
- Updated [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) with full installer verification checkboxes.
- Updated [CHANGELOG.md](CHANGELOG.md) with `v0.4.0` release notes.

---

## 12. Automated Test Results

- **Backend Pytest Suite:** 195/195 PASSED
- **Frontend UI/UX Suite (`npm test`):** 37/37 PASSED
- **Playback Lifecycle Suite:** 6/6 PASSED
- **Client Pitch & Feedback Suite:** 7/7 PASSED
- **Client Calibration Metrics Suite:** 5/5 PASSED
- **Code Style (`git diff --check`):** Clean (0 errors)

---

## 13. Release Artifact Recommendation

The following artifact is prepared and recommended to be uploaded to the **GitHub Release `v0.4.0`**:

| Release Asset Filename | Platform | Size | SHA-256 Checksum |
|---|---|:---:|---|
| `HotChords-v0.4.0-macOS-AppleSilicon.dmg` | macOS (Apple Silicon) | 20 MB | `49d8008569c1b88b027149eeb4c5a4fc8804f650a55a2cf4adf338d6d843404f` |

---

## 14. Remaining Blockers
- **None.** The installer build pipeline and application bundle are fully verified and ready.

---

## 15. Final Installer Verdict: **READY**
The HotChords `v0.4.0` installer has been successfully built from the current clean working tree, mounted, verified, and checksummed.
