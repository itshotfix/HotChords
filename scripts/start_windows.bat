@echo off
setlocal enabledelayedexpansion

title HotChords

:: ──────────────────────────────────────────────────
::  Navigate to project root (one directory up from scripts/)
:: ──────────────────────────────────────────────────
cd /d "%~dp0.."

:: ──────────────────────────────────────────────────
::  Check virtual environment
:: ──────────────────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo   [ERROR] Virtual environment not found.
    echo.
    echo   Please run setup first:
    echo     scripts\setup_windows.bat
    echo.
    pause
    exit /b 1
)

:: ──────────────────────────────────────────────────
::  Activate and launch
:: ──────────────────────────────────────────────────
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Failed to activate virtual environment.
    echo   Try running scripts\setup_windows.bat again.
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   Starting HotChords...
echo ==================================================
echo.
echo   The browser will open automatically.
echo   Press Ctrl+C to stop the server.
echo.

python hotchords.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] HotChords stopped unexpectedly.
    echo.
    echo   Common fixes:
    echo     1. Run scripts\setup_windows.bat to verify dependencies.
    echo     2. Check if port 5500 is in use by another application.
    echo     3. See docs\TROUBLESHOOTING.md for more help.
    echo.
    pause
)
