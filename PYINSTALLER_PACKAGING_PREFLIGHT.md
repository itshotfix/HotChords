# HotChords — PyInstaller Packaging Preflight Audit

**Audit Date**: 2026-09-13  
**Target Release**: v0.4.0  
**Inspection Mode**: Static Code & Architecture Preflight (Zero Build Operations)  

---

## 1. Audit Summary Matrix

| Section | Audit Topic | Result | Summary |
| :--- | :--- | :--- | :--- |
| **1** | **PyInstaller Configuration** | **PASS** | `scripts/build_macos_dmg.sh` and `scripts/build_windows_installer.ps1` include all core runtime modules (`uvicorn.logging`, `uvicorn.loops`, `uvicorn.protocols.http`, `uvicorn.lifespan`, `soundfile`, `scipy.special.cython_special`), full package collection for `librosa` and `imageio_ffmpeg`, and dynamic fallback for optional ML separation. |
| **2** | **Data Files & Assets** | **PASS** | Bundles `frontend/` (HTML, `piano.css`, JS modules, audio assets) and `test songs/`. No non-redistributable model weights are bundled. |
| **3** | **FFmpeg Resolution** | **PASS** | `hotchords.py` dynamically queries `imageio_ffmpeg.get_ffmpeg_exe()` and injects its directory into `os.environ["PATH"]`. Zero reliance on host Homebrew or system FFmpeg. |
| **4** | **Python Runtime & Launcher** | **PASS** | The macOS bundle executes the compiled PyInstaller binary (`HotChords.app/Contents/MacOS/HotChords`). Zero host Python searches (`command -v python3`, `/opt/homebrew`, `/usr/local`) exist at end-user runtime. |
| **5** | **Resource Paths & Portability** | **PASS** | `backend/api/router.py` dynamically resolves static assets relative to `sys._MEIPASS` or `sys.executable`. Zero hardcoded machine paths (`/Users/`, `/Volumes/`, `/tmp/`) exist in runtime logic. |
| **6** | **Port & Dynamic URL Selection** | **PASS** | Uses `get_free_port(start_port=5500)` to scan `5500..5600`. Canonical application address `http://hotchords.localhost:<ACTUAL_PORT>` is dynamically constructed and bound strictly to `127.0.0.1`. |
| **7** | **Startup Sequence & Browser Launch** | **PASS** | Dedicated background thread polls `http://127.0.0.1:<PORT>/health` with 30 retries. Browser launch is triggered **only after** HTTP 200 is confirmed. |

---

## 2. Detailed Technical Audit

### 1. PyInstaller Configuration & Module Coverage
- **Windows Packaging**: `scripts/build_windows_installer.ps1` uses PyInstaller `--onedir --windowed` with hidden imports:
  - `uvicorn.logging`, `uvicorn.loops`, `uvicorn.loops.auto`, `uvicorn.protocols`, `uvicorn.protocols.http`, `uvicorn.protocols.http.auto`, `uvicorn.lifespan`, `uvicorn.lifespan.on`
  - `soundfile`, `imageio_ffmpeg`, `scipy.special.cython_special`
  - Package collection: `--collect-all "librosa"`, `--collect-all "imageio_ffmpeg"`
- **macOS Packaging**: `scripts/build_macos_dmg.sh` mirrors this exact configuration using POSIX data separators (`--add-data "frontend:frontend"`), bundling a standalone macOS app bundle (`HotChords.app`).

### 2. Data Files & Model Weights
- **Included**:
  - `frontend/index.html` (single-workspace UI)
  - `frontend/css/piano.css` (unified responsive stylesheet)
  - `frontend/js/` (`audio/`, `ui/`, `engine/`, `animations/`)
  - `frontend/audio/` (Salamander Grand Piano samples and acoustic synthesizers)
  - `test songs/`
- **Weight Redistribution Policy**:
  - Prohibited weights are **not** bundled.
  - Demucs source separation is architected with graceful fallback: if torch/demucs weights are unavailable offline, HotChords falls back cleanly to harmonic chroma consensus without crashing.

### 3. FFmpeg Runtime Resolution
- **Mechanism**:
  ```python
  # hotchords.py
  try:
      import imageio_ffmpeg
      ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
      ffmpeg_dir = os.path.dirname(ffmpeg_exe)
      os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
  except ImportError:
      pass
  ```
- Because `imageio_ffmpeg` is bundled via `--collect-all "imageio_ffmpeg"`, the precompiled standalone FFmpeg binary is extracted and injected into the execution path on both macOS (Apple Silicon ARM64) and Windows (x64).
- End users do **not** need Homebrew, system FFmpeg, or terminal commands.

### 4. Self-Contained Python Runtime
- **macOS Application Binary**: `HotChords.app/Contents/MacOS/HotChords` is a standalone Mach-O executable containing the embedded Python C runtime and linked dylibs.
- **Audit for Host Search Invocations**:
  - `command -v python3`: **0 occurrences in runtime code**
  - `/opt/homebrew/bin/python3`: **0 occurrences in runtime code**
  - `/usr/local/bin/python3`: **0 occurrences in runtime code**
- Host Python is utilized **only** by the developer build machine during the compilation step.

### 5. Runtime Resource Resolution
- **File**: `backend/api/router.py` (`_get_frontend_dir()`)
  ```python
  def _get_frontend_dir() -> str:
      import sys
      if getattr(sys, "frozen", False):
          if hasattr(sys, "_MEIPASS"):
              bundle_dir = os.path.join(sys._MEIPASS, "frontend")
              if os.path.isdir(bundle_dir):
                  return os.path.abspath(bundle_dir)
          exe_dir = os.path.join(os.path.dirname(sys.executable), "frontend")
          if os.path.isdir(exe_dir):
              return os.path.abspath(exe_dir)
      return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
  ```
- All path lookups are dynamic and relative to `_MEIPASS` or `sys.executable`. Zero absolute development paths exist.

### 6. Dynamic Port & Canonical Localhost URL
- **Port Search**: `get_free_port(start_port=5500)` tests socket availability starting at 5500 across 100 ports (`5500..5600`).
- **Domain Formatting**: `get_app_url(PORT)` formats `http://hotchords.localhost:<PORT>`.
- **Security Binding**: Uvicorn binds strictly to `host="127.0.0.1"`, preventing unauthorized network exposure.

### 7. Startup Lifecycle & Synchronized Browser Launch
```
    [Executable Start (HotChords.exe / HotChords.app)]
                            │
                            ▼
           [Dynamic Port Resolution (e.g. 5502)]
                            │
                            ▼
             [Print Ready Banner to Console]
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    [Spawn Background Thread]   [Start ASGI Server (Uvicorn)]
              │                           │
    [Poll /health every 0.5s]             │
              │                           │
    [HTTP 200 "ready" Received] <─────────┘ (Server Listening on 127.0.0.1)
              │
              ▼
   [webbrowser.open(http://hotchords.localhost:<PORT>)]
   [Display macOS Native User Notification]
```
The browser is never launched before the server responds to the health probe.

---

## 3. Runtime Risks Identified for Release Gate Testing

The following items cannot be 100% verified statically without executing the full binary build on the target operating system:

1. **macOS Gatekeeper & Code Signing**:
   - macOS Sequoia / Sonoma enforces quarantine flags (`com.apple.quarantine`) on DMGs downloaded from web browsers.
   - An ad-hoc signed or unsigned PyInstaller bundle may require the user to right-click -> "Open" on first launch or run `xattr -cr /Applications/HotChords.app`.
2. **C-Extension Linkage (librosa / soundfile / libsndfile)**:
   - `soundfile` bundles `libsndfile` dylibs/DLLs. The PyInstaller hook `--collect-all "librosa"` and `--hidden-import "soundfile"` must ensure `_soundfile_data` dylibs are embedded without missing loader rpaths.
3. **First-Run Stem Separation Model Download**:
   - If Demucs stem separation is invoked on a clean machine with internet, PyTorch downloads `htdemucs` (~80MB) to `~/.cache/torch/hub/checkpoints/`. If offline, separation degrades gracefully to non-separated harmonic extraction without application crashes.
