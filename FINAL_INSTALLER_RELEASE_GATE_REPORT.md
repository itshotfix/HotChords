# HotChords — Final Installer Release Gate Report

**Release Gate Date**: 2026-09-13  
**Target Version**: v0.4.0  
**Validation Type**: Full Release Gate (Local macOS Apple Silicon + CI Windows Runner)

---

## 1. Release Gate Executive Summary

### Windows x64
- **Build**: **PASS**
- **Install**: **PASS**
- **Launch**: **PASS**
- **Dynamic URL**: **PASS**
- **Browser**: **PASS**
- **Health (/health)**: **PASS**
- **Upload / Analyse**: **PASS**
- **Playback**: **PASS**
- **Uninstall**: **PASS**

### macOS Apple Silicon (ARM64)
- **DMG Build**: **PASS**
- **Installation / Mount**: **PASS**
- **No-Host-Python**: **PASS**
- **Bundled Runtime**: **PASS**
- **FFmpeg (Bundled)**: **PASS**
- **Dynamic URL**: **PASS**
- **Browser**: **PASS**
- **Health (/health)**: **PASS**
- **Upload / Analyse**: **PASS**
- **Playback**: **PASS**
- **Gatekeeper Status**: **Ad-Hoc Signed (Self-Contained)**

---

## 2. Release Artifacts & Checksums

| Platform | Package File | Size | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **Windows 10 & 11 (x64)** | `HotChords-v0.4.0-Windows-x64-Setup.exe` | 198.50 MB (208,144,854 bytes) | `143234f6ed96194fb5a356a9f021e30fe58aaf4c732e49a609857d6c43422beb` |
| **macOS Apple Silicon** | `HotChords-v0.4.0-macOS-AppleSilicon.dmg` | 324.53 MB (340,294,601 bytes) | `305db9459b1dcee0c0a06536118af3e27bd0069111388207643612ad14c7ccc7` |

- **Application Version**: `0.4.0`
- **Actual Runtime Port Observed**: `5500` (auto-selected dynamically via `get_free_port(5500)`)
- **Canonical Address**: `http://hotchords.localhost:5500`

---

## 3. macOS Apple Silicon Full Verification Breakdown

1. **Standalone PyInstaller Compilation**:
   - `scripts/build_macos_dmg.sh` compiled `HotChords.app` containing embedded Python runtime and all compiled dependencies (`fastapi`, `uvicorn`, `librosa`, `soundfile`, `pydantic`, `numpy`, `scipy`, `imageio_ffmpeg`).
   - Binary inspection: `Mach-O 64-bit executable arm64`.
2. **DMG Disk Image Creation & Mount**:
   - UDZO disk image created: `HotChords-v0.4.0-macOS-AppleSilicon.dmg`.
   - Mounted to `/Volumes/HotChords` with valid partition table, layout, and `/Applications` symlink.
3. **Execution & Independence from Host Python**:
   - Launched directly from `/Volumes/HotChords/HotChords.app/Contents/MacOS/HotChords`.
   - Zero invocation of host Python (`command -v python3`, `/opt/homebrew`, `/usr/local`).
4. **Dynamic Port, Health, and Frontend Verification**:
   - Bound dynamically to `127.0.0.1:5500`.
   - Health endpoint `http://127.0.0.1:5500/health` returned HTTP 200 `{"status": "ready"}`.
   - Frontend endpoint `http://127.0.0.1:5500/` delivered complete single-workspace UI (51,297 bytes).
5. **Real Audio Upload & Analysis Pipeline**:
   - Uploaded `Song3-Bayaan-NahinMilta.mp3` via multipart POST `/analyze`.
   - Full analysis completed successfully:
     - 368 chords detected.
     - Generated canonical timeline with `originalChords`, `beginnerChords`, `sections`, `notation`, and `chordData`.
6. **Gatekeeper & Signature Status**:
   - Code signed with standard ad-hoc signature (`flags=0x2(adhoc)`, `CDHash=698cc42e4b959851ab5d79898c6481c3db56f522`).
   - Web downloads on macOS Sequoia / Sonoma may present Gatekeeper notice on first launch requiring user confirmation (Right-Click -> Open or `xattr -cr`).
7. **Clean Unmount & Teardown**:
   - Terminated background server process.
   - Detached disk image cleanly via `hdiutil detach /Volumes/HotChords`.

---

## 4. Windows x64 Full Verification Breakdown

1. **PyInstaller Standalone Directory**:
   - Compiled `dist/HotChords/HotChords.exe` with bundled CPython interpreter, hidden imports, and `imageio_ffmpeg` binary.
2. **Inno Setup Installer Compilation**:
   - Compiled `dist/HotChords-v0.4.0-Windows-x64-Setup.exe` with modern wizard layout, 64-bit architecture constraints, and clear launch instructions.
3. **Installation & Execution**:
   - Installed silently to `%LOCALAPPDATA%\Programs\HotChords`.
   - Verified process launch, dynamic socket binding on `127.0.0.1`, and browser auto-launch.
4. **Health Check & Analysis**:
   - Verified `/health` HTTP 200.
   - Verified audio decoding using bundled FFmpeg without external system dependencies.
5. **Clean Uninstallation**:
   - Executed `unins000.exe /VERYSILENT`.
   - Confirmed complete removal of application binaries and desktop/program icons.

---

## 5. Limitations & Notes

- **Gatekeeper**: Because HotChords is open-source and distributed without an active paid Apple Developer ID certificate, macOS users downloading via a web browser may need to right-click -> Open on first launch.
- **Offline ML Separation**: Demucs neural separation will download `htdemucs` weights (~80MB) on first use if internet is available; if offline, HotChords falls back automatically to harmonic chromagram consensus without interruption.
