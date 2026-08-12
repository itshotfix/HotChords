#!/usr/bin/env bash
set -e

echo ""
echo "=================================================="
echo "  HotChords Setup for macOS / Linux"
echo "=================================================="
echo ""

# ──────────────────────────────────────────────────
#  Navigate to project root (one directory up from scripts/)
# ──────────────────────────────────────────────────
cd "$(dirname "$0")/.." || { echo "  [ERROR] Could not navigate to project root."; exit 1; }

# ──────────────────────────────────────────────────
#  Step 1: Detect Python
# ──────────────────────────────────────────────────
echo "[Step 1/6] Checking for Python..."

PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo ""
    echo "  [ERROR] Python 3 was not found on your system."
    echo ""
    echo "  Install Python 3.10, 3.11, or 3.12:"
    echo "    macOS:  brew install python@3.11"
    echo "    Linux:  sudo apt install python3"
    echo ""
    exit 1
fi

echo "  Found: $PYTHON_CMD"

# ──────────────────────────────────────────────────
#  Step 2: Validate Python version (3.10 - 3.12)
# ──────────────────────────────────────────────────
echo "[Step 2/6] Checking Python version..."

PY_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" != "3" ]; then
    echo ""
    echo "  [ERROR] Python $PY_VERSION is not supported."
    echo "  HotChords requires Python 3.10, 3.11, or 3.12."
    exit 1
fi

if [ "$PY_MINOR" -lt 10 ]; then
    echo ""
    echo "  [ERROR] Python $PY_VERSION is too old."
    echo "  HotChords requires Python 3.10, 3.11, or 3.12."
    echo ""
    echo "  macOS:  brew install python@3.11"
    echo "  Linux:  sudo apt install python3.11"
    exit 1
fi

if [ "$PY_MINOR" -gt 12 ]; then
    echo "  [WARNING] Python $PY_VERSION is newer than the tested range (3.10-3.12)."
    echo "  Setup will continue, but some dependencies may not be compatible."
    echo ""
fi

echo "  Python $PY_VERSION — OK"

# ──────────────────────────────────────────────────
#  Step 3: Create virtual environment
# ──────────────────────────────────────────────────
echo "[Step 3/6] Setting up virtual environment..."

if [ ! -f "venv/bin/activate" ]; then
    echo "  Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo ""
        echo "  [ERROR] Failed to create virtual environment."
        echo "  Make sure the venv module is available:"
        echo "    sudo apt install python3-venv  (Linux/Debian)"
        exit 1
    fi
    echo "  Virtual environment created."
else
    echo "  Virtual environment already exists — skipping creation."
fi

# ──────────────────────────────────────────────────
#  Step 4: Activate and install dependencies
# ──────────────────────────────────────────────────
echo "[Step 4/6] Installing dependencies..."

source venv/bin/activate

# Upgrade pip quietly
python3 -m pip install --upgrade pip > /dev/null 2>&1

# Install/upgrade requirements
pip install --upgrade -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "  [ERROR] Failed to install dependencies."
    echo ""
    echo "  Common fixes:"
    echo "    1. Make sure you have an internet connection."
    echo "    2. If PyTorch fails on Apple Silicon, try:"
    echo "       pip install torch --index-url https://download.pytorch.org/whl/cpu"
    echo "    3. On Linux, you may need: sudo apt install python3-dev build-essential"
    exit 1
fi

echo "  Dependencies installed successfully."

# ──────────────────────────────────────────────────
#  Step 5: Verify critical dependencies
# ──────────────────────────────────────────────────
echo "[Step 5/6] Verifying installation..."

# Check FFmpeg
python3 -c "import imageio_ffmpeg; print('  FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  [WARNING] FFmpeg verification failed."
    echo "  Audio file loading may not work for MP3/M4A formats."
    echo "  Try: pip install imageio-ffmpeg"
fi

# Check librosa
python3 -c "import librosa; print('  librosa:', librosa.__version__)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  [ERROR] librosa could not be imported. Audio analysis will not work."
    exit 1
fi

# Check fastapi
python3 -c "import fastapi; print('  FastAPI:', fastapi.__version__)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  [ERROR] FastAPI could not be imported. The server will not start."
    exit 1
fi

# Check torch (optional)
python3 -c "import torch; print('  PyTorch:', torch.__version__)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  [INFO] PyTorch not available — Demucs AI separation will be skipped."
    echo "  Chord detection will still work using the standard audio pipeline."
fi

# ──────────────────────────────────────────────────
#  Step 6: Verify project structure
# ──────────────────────────────────────────────────
echo "[Step 6/6] Checking project structure..."

if [ ! -f "frontend/index.html" ]; then
    echo "  [ERROR] frontend/index.html not found."
    echo "  Make sure you cloned the complete HotChords repository."
    exit 1
fi

if [ ! -f "hotchords.py" ]; then
    echo "  [ERROR] hotchords.py not found."
    echo "  Make sure you are running setup from the HotChords project folder."
    exit 1
fi

echo "  Project structure — OK"

# ──────────────────────────────────────────────────
#  Done
# ──────────────────────────────────────────────────
echo ""
echo "=================================================="
echo "  Setup Complete!"
echo "=================================================="
echo ""
echo "  To start HotChords, run:"
echo "    bash scripts/start_mac.sh"
echo ""
