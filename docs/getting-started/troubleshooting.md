# HotChords — Troubleshooting Guide

This guide covers common issues when setting up and running HotChords on Windows and macOS.

---

## Windows

### Python Not Found

**Symptom:** `[ERROR] Python was not found on your system.`

**Fix:**
1. Download Python 3.10, 3.11, or 3.12 from [python.org](https://www.python.org/downloads/).
2. During installation, **check the box** that says **"Add Python to PATH"**. This is critical.
3. After installation, **close and reopen** your terminal or Command Prompt.
4. Verify by running: `python --version` or `py --version`.

If Python is installed but not found, it was likely installed without adding it to PATH. You can either:
- Reinstall Python with the PATH checkbox enabled.
- Manually add Python to your system PATH via *Settings → System → Advanced system settings → Environment Variables*.

---

### pip Installation Failure

**Symptom:** `[ERROR] Failed to install dependencies.`

**Common causes:**

1. **No internet connection.** pip needs to download packages. Check your connection.

2. **Microsoft Visual C++ Build Tools required.** Some Python packages (like NumPy, SciPy) require C compilation on Windows. Install the [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and try again.

3. **Antivirus blocking downloads.** Some antivirus software blocks pip from downloading packages. Temporarily disable real-time scanning and try again.

4. **Proxy or firewall.** If you're on a corporate network, pip may need proxy configuration:
   ```cmd
   pip install --proxy http://your-proxy:port -r requirements.txt
   ```

---

### PyTorch Installation Issues

**Symptom:** PyTorch fails to install or takes a very long time.

**Fix:** PyTorch is a large package (~2GB). On slow connections, installation may time out.

To install PyTorch with CPU-only support (smaller download, no NVIDIA GPU required):
```cmd
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

If you have an NVIDIA GPU and want GPU acceleration, install the CUDA version:
```cmd
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Note:** PyTorch/Demucs is optional. HotChords chord detection works without it. Demucs provides AI-powered vocal/instrument separation which can improve chord detection accuracy, but the core pipeline works fine without it.

---

### FFmpeg Not Available

**Symptom:** `[WARNING] FFmpeg verification failed` or audio files fail to load.

HotChords bundles FFmpeg via the `imageio-ffmpeg` Python package. If this isn't working:

1. Verify the package is installed:
   ```cmd
   pip install imageio-ffmpeg>=0.4.9
   ```
2. Test it:
   ```cmd
   python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
   ```
3. If the bundled FFmpeg doesn't work, install FFmpeg system-wide:
   ```cmd
   winget install ffmpeg
   ```

**Note:** WAV and FLAC files load without FFmpeg (via `soundfile`). FFmpeg is primarily needed for MP3, M4A, OGG, and AAC formats.

---

### Demucs / AI Separation is Slow

**Symptom:** The progress bar is stuck at "Separating vocals and instruments..." for a long time.

**This is expected on CPU.** Demucs AI separation is computationally intensive:
- **With NVIDIA GPU (CUDA):** ~30 seconds per song.
- **With Apple Silicon (MPS):** ~1-2 minutes per song.
- **CPU only:** ~5-15 minutes per song, depending on hardware.

HotChords automatically detects and uses the best available hardware. If processing is too slow, the pipeline will still produce results — it just takes longer.

If you want to skip AI separation entirely and use the faster standard pipeline, Demucs will be skipped automatically if PyTorch is not installed.

---

### Port Already in Use

**Symptom:** `[ERROR] HotChords stopped unexpectedly` or the browser opens but shows an error page.

HotChords defaults to port 5500 and automatically tries the next available port if 5500 is occupied. However, if many ports are in use:

1. Check what's using port 5500:
   ```cmd
   netstat -aon | findstr :5500
   ```
2. Close the application using that port, or let HotChords pick another one (it will display the actual URL in the terminal).

---

### Antivirus Blocking the Application

**Symptom:** Windows Defender or antivirus software flags HotChords scripts or Python processes.

HotChords runs a local Python web server. Some antivirus software may:
- Block the `python.exe` process from listening on a network port.
- Flag `.bat` scripts as potentially harmful.

**Fix:**
1. Add the HotChords project folder to your antivirus exclusion list.
2. Add `python.exe` (in the `venv\Scripts\` folder) to the exclusion list.
3. When Windows Defender SmartScreen blocks a `.bat` file, click "More info" → "Run anyway".

---

### Browser Does Not Open Automatically

**Symptom:** The server starts but no browser window appears.

HotChords uses the system's default browser. If auto-open fails:
1. Open your browser manually.
2. Navigate to the URL shown in the terminal (usually `http://localhost:5500`).
3. Check the terminal output for the actual port number if 5500 was occupied.

---

## macOS

### Python Version Issues

**Symptom:** `[ERROR] Python ... is too old` or unexpected behavior.

macOS comes with a system Python that may be outdated. Install a modern version:

```bash
brew install python@3.11
```

After installation, verify:
```bash
python3 --version
```

If `python3` still points to the old version, use the full path:
```bash
/opt/homebrew/bin/python3.11 -m venv venv
```

---

### FFmpeg on macOS

The `imageio-ffmpeg` package bundles FFmpeg, so you typically don't need to install it separately. However, if you encounter audio loading issues:

```bash
brew install ffmpeg
```

---

### Permission Denied

**Symptom:** `bash: scripts/setup_mac.sh: Permission denied`

**Fix:**
```bash
chmod +x scripts/setup_mac.sh scripts/start_mac.sh
```

Or run with bash explicitly:
```bash
bash scripts/setup_mac.sh
```

---

### Port Conflicts on macOS

**Symptom:** Server fails to start or error about port in use.

Check what's using port 5500:
```bash
lsof -i :5500
```

Kill the process if needed:
```bash
kill -9 <PID>
```

HotChords automatically tries alternate ports (5501, 5502, etc.) if 5500 is occupied.

---

## General

### Supported Audio Formats

HotChords supports the following audio formats:
- **WAV** — Best compatibility, loads via `soundfile`
- **FLAC** — Lossless, loads via `soundfile`
- **MP3** — Loads via `soundfile` (with modern `libsndfile`) or FFmpeg fallback
- **M4A / AAC** — Requires FFmpeg
- **OGG** — Loads via `soundfile` or FFmpeg fallback

If a specific format fails to load, try converting it to WAV first using any audio converter.

### Processing Time

Processing time depends on song length and hardware:

| Step | CPU | GPU (CUDA/MPS) |
|------|-----|----------------|
| Audio loading | 1-3s | 1-3s |
| Demucs separation | 5-15 min | 30s-2 min |
| Chroma + beat tracking | 3-10s | 3-10s |
| Viterbi HMM | <1s | <1s |

Songs without Demucs separation typically process in under 30 seconds.

### Memory Requirements

- **Without Demucs:** ~500MB RAM
- **With Demucs (CPU):** ~2-4GB RAM
- **With Demucs (GPU):** ~3GB VRAM + ~2GB RAM

### Running the Environment Check

HotChords includes a built-in diagnostic tool:

```bash
# macOS / Linux
python3 -m backend.utils.preflight

# Windows
python -m backend.utils.preflight
```

This checks Python version, packages, FFmpeg, and project structure without performing any audio analysis.

---

## Still Having Issues?

1. Run the environment check: `python -m backend.utils.preflight`
2. Check the terminal output for error messages.
3. Open an issue on [GitHub](https://github.com/hotfix/hotchords/issues) with:
   - Your OS and Python version
   - The full terminal output
   - The audio format you're trying to load
