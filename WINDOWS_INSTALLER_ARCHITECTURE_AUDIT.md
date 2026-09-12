# Windows Installer Architecture Audit & Packaging Specification

## 1. Application Architecture & Entry Points

HotChords is an interactive, local-first music workstation comprising a FastAPI/Uvicorn ASGI backend and a vanilla HTML5/CSS/JavaScript frontend with Web Audio and Salamander Grand Piano synthesis.

### 1.1 Startup & Process Lifecycle
- **Entry Point:** `hotchords.py` and `backend/main.py`.
- **Server Binding:** FastAPI application served via Uvicorn on localhost (`127.0.0.1`), default port range starting at `5500` / `5501` (managed dynamically by `get_free_port`).
- **Browser Auto-Open:** `open_browser()` runs in a daemon thread, polling `http://localhost:{PORT}` via HTTP requests every 500ms (up to 20 retries). `webbrowser.open()` is triggered **only after** the HTTP server returns a valid response, guaranteeing that the browser never opens to a connection error.
- **Shutdown:** Standard process termination signals (SIGINT / SIGTERM / Ctrl+C / process close) cleanly shut down the Uvicorn server and background threads.

---

## 2. Path Handling & Static Asset Resolution

### 2.1 Static Assets
- `frontend/` directory contains `index.html`, `css/`, `js/`, and `audio/` (Salamander Grand Piano samples).
- Static assets are mounted via FastAPI `StaticFiles`.
- **Frozen Environment Support:** When packaged with PyInstaller, `sys._MEIPASS` or `os.path.dirname(sys.executable)` must be checked so asset paths resolve seamlessly whether running from source or inside a packaged bundle.

### 2.2 Temporary Files & Caches
- `STEMS_DIR` defaults to `os.path.join(tempfile.gettempdir(), 'hotchords_stems')`.
- Uploaded audio files are stored in standard user temporary directories via `tempfile.mkstemp()`.
- On Windows, this resolves to `%LOCALAPPDATA%\Temp\hotchords_stems`, which does not require administrator privileges and keeps user data local and private.

---

## 3. Dependency Classification

### 3.1 Runtime Dependencies (Mandatory in Bundle)
- `fastapi`, `uvicorn`, `pydantic`, `python-multipart` (API & Web Server)
- `numpy`, `scipy`, `soundfile`, `librosa` (Signal Processing, CQT, HPSS, Chroma)
- `imageio-ffmpeg` (Provides platform-specific standalone FFmpeg executable)
- `audioop-lts` (Standard audio utility support for Python 3.13+)
- `lv-chordia` & `torch` (Deep neural chord recognition ensemble; fallback to CQT chroma if bypassed)
- `demucs` (Stem separation; graceful fallback if unaccelerated or bypassed)

### 3.2 Development / Test Dependencies (Excluded from Installer)
- `pytest`, `pytest-cov`
- Node.js / `npm` test harnesses (`package.json`)
- Benchmarking scripts and synthetic data generators

---

## 4. FFmpeg & Audio Codec Strategy

- **Strategy:** Bundled via `imageio-ffmpeg` prebuilt Windows x64 binary (`imageio_ffmpeg.get_ffmpeg_exe()`).
- In `hotchords.py`, the directory of the bundled FFmpeg binary is automatically injected into `os.environ["PATH"]`.
- **User Experience:** Zero terminal commands, zero PATH configuration, and zero manual software installations required from Windows end users. Full support for MP3, WAV, FLAC, and M4A is preserved out of the box.

---

## 5. Machine Learning & Model Weight Strategy

- **LV-Chordia:** Pretrained models are lightweight PyTorch modules packaged with the library or cached under standard user cache directories (`%USERPROFILE%\.cache`).
- **Demucs:** Uses `htdemucs` model weights cached in `%USERPROFILE%\.cache\torch\hub\checkpoints`. If unavailable or offline, the pipeline automatically bypasses stem separation and executes HPSS + multi-source consensus on the master mix without throwing fatal runtime errors.

---

## 6. Windows Target & Installer Architecture

- **Operating System:** Windows 10 & Windows 11 (64-bit)
- **Architecture:** x86-64 / AMD64 (Intel & AMD)
- **Packaging Chain:**
  1. **PyInstaller:** Bundles Python 3.11 runtime, compiled C extensions, PyTorch, and backend modules into a standalone distribution folder (`dist/HotChords`).
  2. **Inno Setup (ISCC):** Packages the standalone distribution into a single modern installer executable: `HotChords-v0.4.0-Windows-x64-Setup.exe`.
- **Installer Features:**
  - Standard Windows wizard with clear application metadata.
  - Installs to `%LOCALAPPDATA%\Programs\HotChords` (no admin privileges required).
  - Creates Start Menu shortcut and optional Desktop icon.
  - Provides a clean uninstaller (`unins000.exe`).
  - Option to launch HotChords immediately upon finish, opening the browser automatically.
- **Code Signing:** Unsigned (documented transparently; Windows SmartScreen prompt guidance provided).
