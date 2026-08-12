@echo off
setlocal enabledelayedexpansion

title HotChords Setup

echo ==================================================
echo   HotChords Setup for Windows
echo ==================================================
echo.

:: ──────────────────────────────────────────────────
::  Navigate to project root (one directory up from scripts/)
:: ──────────────────────────────────────────────────
cd /d "%~dp0.."

:: ──────────────────────────────────────────────────
::  Step 1: Detect Python
:: ──────────────────────────────────────────────────
echo [Step 1/6] Checking for Python...

set PYTHON_CMD=
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=py
    goto :found_python
)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_CMD=python
    goto :found_python
)

echo.
echo   [ERROR] Python was not found on your system.
echo.
echo   Please install Python 3.10, 3.11, or 3.12 from:
echo     https://www.python.org/downloads/
echo.
echo   IMPORTANT: During installation, check the box:
echo     "Add Python to PATH"
echo.
echo   After installing Python, run this setup script again.
echo.
pause
exit /b 1

:found_python
echo   Found: %PYTHON_CMD%

:: ──────────────────────────────────────────────────
::  Step 2: Validate Python version (3.10 - 3.12)
:: ──────────────────────────────────────────────────
echo [Step 2/6] Checking Python version...

for /f "tokens=2 delims= " %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VERSION=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if "%PY_MAJOR%" neq "3" (
    echo.
    echo   [ERROR] Python %PY_VERSION% is not supported.
    echo   HotChords requires Python 3.10, 3.11, or 3.12.
    echo   Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

set /a PY_MINOR_NUM=%PY_MINOR%
if %PY_MINOR_NUM% lss 10 (
    echo.
    echo   [ERROR] Python %PY_VERSION% is too old.
    echo   HotChords requires Python 3.10, 3.11, or 3.12.
    echo   Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

if %PY_MINOR_NUM% gtr 12 (
    echo   [WARNING] Python %PY_VERSION% is newer than the tested range ^(3.10-3.12^).
    echo   Setup will continue, but some dependencies may not be compatible.
    echo.
)

echo   Python %PY_VERSION% — OK

:: ──────────────────────────────────────────────────
::  Step 3: Create virtual environment
:: ──────────────────────────────────────────────────
echo [Step 3/6] Setting up virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo   Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo.
        echo   [ERROR] Failed to create virtual environment.
        echo   Make sure the 'venv' module is available.
        echo   Try: %PYTHON_CMD% -m ensurepip
        echo.
        pause
        exit /b 1
    )
    echo   Virtual environment created.
) else (
    echo   Virtual environment already exists — skipping creation.
)

:: ──────────────────────────────────────────────────
::  Step 4: Activate and install dependencies
:: ──────────────────────────────────────────────────
echo [Step 4/6] Installing dependencies...

call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Failed to activate virtual environment.
    echo   Try deleting the 'venv' folder and running setup again.
    echo.
    pause
    exit /b 1
)

:: Upgrade pip quietly
python -m pip install --upgrade pip >nul 2>nul

:: Install/upgrade requirements
pip install --upgrade -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Failed to install dependencies.
    echo.
    echo   Common fixes:
    echo     1. Make sure you have an internet connection.
    echo     2. If you see "Microsoft Visual C++ required", install:
    echo        https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo     3. If PyTorch fails, try installing without GPU support:
    echo        pip install torch --index-url https://download.pytorch.org/whl/cpu
    echo.
    pause
    exit /b 1
)

echo   Dependencies installed successfully.

:: ──────────────────────────────────────────────────
::  Step 5: Verify critical dependencies
:: ──────────────────────────────────────────────────
echo [Step 5/6] Verifying installation...

:: Check FFmpeg
python -c "import imageio_ffmpeg; print('  FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [WARNING] FFmpeg verification failed.
    echo   Audio file loading may not work for MP3/M4A formats.
    echo   Try: pip install imageio-ffmpeg
)

:: Check librosa
python -c "import librosa; print('  librosa:', librosa.__version__)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [ERROR] librosa could not be imported. Audio analysis will not work.
    pause
    exit /b 1
)

:: Check fastapi
python -c "import fastapi; print('  FastAPI:', fastapi.__version__)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [ERROR] FastAPI could not be imported. The server will not start.
    pause
    exit /b 1
)

:: Check torch (optional)
python -c "import torch; print('  PyTorch:', torch.__version__)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [INFO] PyTorch not available — Demucs AI separation will be skipped.
    echo   Chord detection will still work using the standard audio pipeline.
)

:: ──────────────────────────────────────────────────
::  Step 6: Verify project structure
:: ──────────────────────────────────────────────────
echo [Step 6/6] Checking project structure...

if not exist "frontend\index.html" (
    echo   [ERROR] frontend\index.html not found.
    echo   Make sure you cloned the complete HotChords repository.
    pause
    exit /b 1
)

if not exist "hotchords.py" (
    echo   [ERROR] hotchords.py not found.
    echo   Make sure you are running setup from the HotChords project folder.
    pause
    exit /b 1
)

echo   Project structure — OK

:: ──────────────────────────────────────────────────
::  Done
:: ──────────────────────────────────────────────────
echo.
echo ==================================================
echo   Setup Complete!
echo ==================================================
echo.
echo   To start HotChords, double-click:
echo     scripts\start_windows.bat
echo.
echo   Or run from this terminal:
echo     scripts\start_windows.bat
echo.
pause
