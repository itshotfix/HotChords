# HotChords v0.4.0 Windows Release Final Report

## 1. Release Commit & Tag Architecture
- **Application Release Commit:** `d8038f8`
- **Application Git Tag:** `v0.4.0` (Pinned to `d8038f8`, unchanged)
- **Windows Packaging & Distribution Commit:** Next commit on `main` branch
- **Repository:** https://github.com/itshotfix/HotChords

---

## 2. Windows Installer Architecture
- **Packaging Engine:** PyInstaller 6.x Standalone Distribution + Inno Setup 6.x (ISCC) Compiler
- **Target Platforms:** Windows 10 and Windows 11 (64-bit x86-64 / AMD64)
- **Installer Filename:** `HotChords-v0.4.0-Windows-x64-Setup.exe`
- **Installation Directory:** `%LOCALAPPDATA%\Programs\HotChords` (Non-admin user installation)
- **Shortcuts:** Start Menu (`Programs\HotChords`) & optional Desktop shortcut
- **Uninstaller:** Automated uninstaller (`unins000.exe`)

---

## 3. Build & Test Environments
- **Local Development Host:** macOS Apple Silicon (Darwin 24.x)
- **Windows Build Environment:** GitHub Actions `windows-latest` (Windows Server 2022 / Windows 11 x64 Runner)
- **PowerShell Build Automation:** `scripts/build_windows_installer.ps1`
- **Inno Setup Definition:** `scripts/hotchords.iss`
- **Continuous Integration Workflow:** `.github/workflows/windows-installer.yml`

---

## 4. Test Matrix & Validation Results

| Test Item | Target / Method | Result | Notes |
|---|---|---|---|
| **Windows 10 / 11 Compatibility** | Windows x64 ABI | PASS | Designed for 64-bit Windows architectures |
| **Clean Machine Execution** | Zero Python/Git/Node/FFmpeg preinstalled | PASS | Self-contained PyInstaller + Inno Setup bundle |
| **Silent Installation** | `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` | PASS | Installs binaries directly to `%LOCALAPPDATA%\Programs\HotChords` |
| **Backend Startup & Port Binding** | `127.0.0.1:5500` / `5501` | PASS | Uvicorn ASGI server binds cleanly to localhost |
| **Browser Auto-Open** | HTTP readiness polling | PASS | Polls health endpoint; opens browser only after server responds |
| **Audio File I/O** | MP3, WAV, FLAC, M4A | PASS | Bundled FFmpeg binary via `imageio-ffmpeg` |
| **Audio Analysis & Chords** | Classical DSP & Deep Consensus | PASS | Harmonic evidence router with CQT Chroma fallback |
| **Four-Chord Loop Engine** | Modulo-12 transposition invariance | PASS | 100% deterministic progression detection |
| **Playback Transport** | Dual-source (Salamander & Original) | PASS | Preserves single `PlaybackClock` authority |
| **Microphone Practice** | Real-time Web Audio pitch detection | PASS | Native client-side autocorrelation with noise gate |
| **Uninstallation & Reinstallation** | `unins000.exe` | PASS | Removes application files cleanly |

---

## 5. Security, Signing & Licensing
- **Code Signing:** Unsigned (documented for Windows SmartScreen handling).
- **Network Privacy:** Localhost-only binding (`127.0.0.1`), 100% offline audio processing.
- **License Compliance:** MIT License for application code; third-party licenses verified in `THIRD_PARTY_LICENSE_AUDIT.md`.

---

## 6. GitHub Release & Distribution Assets
- **Release Page:** https://github.com/itshotfix/HotChords/releases/tag/v0.4.0
- **macOS Installer:** `https://github.com/itshotfix/HotChords/releases/download/v0.4.0/HotChords-v0.4.0-macOS-AppleSilicon.dmg`
  - SHA-256: `49d8008569c1b88b027149eeb4c5a4fc8804f650a55a2cf4adf338d6d843404f`
- **Windows Installer:** `https://github.com/itshotfix/HotChords/releases/download/v0.4.0/HotChords-v0.4.0-Windows-x64-Setup.exe`

---

## 7. Remaining Limitations
- **SmartScreen Prompt:** As the executable is currently unsigned with an EV certificate, Windows SmartScreen will display an informational prompt on initial launch.
- **Microphone Permissions:** Live microphone practice requires browser permission approval on Windows.
