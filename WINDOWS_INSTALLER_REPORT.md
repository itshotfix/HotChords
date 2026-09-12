# HotChords v0.4.0 Windows Installer Report

## 1. Executive Summary

HotChords v0.4.0 has been packaged into a standalone Windows installer (`HotChords-v0.4.0-Windows-x64-Setup.exe`) targeting Windows 10 and Windows 11 64-bit systems. The packaging eliminates all prerequisite setup for end users: no system Python, Git, Node.js, npm, or FFmpeg installations are required.

---

## 2. Packaging Architecture

- **Engine:** PyInstaller 6.x + Inno Setup 6.x (ISCC)
- **Target OS:** Windows 10 & Windows 11 (64-bit x86-64 / AMD64)
- **Installer Filename:** `HotChords-v0.4.0-Windows-x64-Setup.exe`
- **Output Directory:** `dist/`
- **Installation Directory:** `%LOCALAPPDATA%\Programs\HotChords` (User-level install, requiring zero administrator privileges)
- **Shortcuts:** Start Menu (`Programs\HotChords`) and optional Desktop icon
- **Uninstaller:** Fully automated uninstaller (`unins000.exe`) that cleans up binary files without affecting unrelated user documents.

---

## 3. Runtime Dependency & Audio Processing Strategy

- **Python Runtime:** Embedded Python 3.11 environment bundled into the application distribution.
- **Audio Processing:** Precompiled binaries for `numpy`, `scipy`, `soundfile`, and `librosa`.
- **FFmpeg Integration:** Bundled platform executable managed via `imageio-ffmpeg`. On startup, `hotchords.py` dynamically injects the binary directory into the process `PATH`, enabling decoding of MP3, WAV, FLAC, and M4A audio files immediately.
- **Machine Learning & Models:**
  - `lv-chordia`: Lightweight PyTorch models bundled in the package for deep chord estimation.
  - `demucs`: Optional stem separation with graceful fallback to HPSS + CQT chroma consensus when unaccelerated or offline.
- **Static Frontend Assets:** `frontend/` assets (HTML, CSS, JS, Salamander Grand Piano samples) are packaged alongside the binary and dynamically resolved at runtime via `_get_frontend_dir()`.

---

## 4. Application Lifecycle & Browser Launch

1. **Launch:** User executes `HotChords.exe` (or clicks Start Menu shortcut).
2. **Server Initialization:** FastAPI backend binds to `127.0.0.1` on an available port starting at `5500` / `5501`.
3. **Readiness Detection:** A background daemon thread polls the server's health endpoint every 500ms.
4. **Browser Open:** Only after receiving a successful HTTP response does the launcher invoke `webbrowser.open()`, ensuring the user never experiences a broken or prematurely loaded browser page.
5. **Termination:** Clean exit on window close or process termination.

---

## 5. Security, Code Signing & Licensing

- **Code Signing Status:** Unsigned. Standard Windows SmartScreen warnings ("Windows protected your PC") may appear upon initial download. Users can click *More info* $\rightarrow$ *Run anyway*.
- **Local Privacy:** 100% offline audio processing. No audio files, metrics, or telemetry are transmitted to cloud services.
- **License Compliance:** HotChords is released under the [MIT License](LICENSE). Third-party dependencies audited in [THIRD_PARTY_LICENSE_AUDIT.md](THIRD_PARTY_LICENSE_AUDIT.md).
