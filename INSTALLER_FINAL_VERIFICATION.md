# HotChords — Final Installer URL & macOS Runtime Verification Report

**Verification Date**: 2026-09-13  
**Target Release**: v0.4.0  
**Repository State**: Inspected without code modification or installer builds  

---

## 1. Verification Summary Table

| Check | Result | Description |
| :--- | :--- | :--- |
| `WINDOWS_FINISHED_PAGE_URL` | **FAIL** | Inno Setup Finished Page runs prior to application startup and cannot display or link to the dynamic runtime port `<ACTUAL_PORT>`. |
| `WINDOWS_DYNAMIC_PORT_HANDLING` | **PASS** | `backend/main.py` dynamically selects an available port (`get_free_port(5500)`), binds Uvicorn, prints the ready banner, and auto-opens `http://hotchords.localhost:<PORT>`. |
| `MACOS_SELF_CONTAINED` | **FAIL** | `scripts/build_macos_dmg.sh` does not package an embedded Python interpreter or site-packages; it copies raw source files and requires host Python. |
| `MACOS_SYSTEM_PYTHON_DEPENDENCY` | **YES** | `scripts/build_macos_dmg.sh` launcher script explicitly searches for and executes system/Homebrew `python3`. |
| `FAST_VALIDATOR_PORT_LOGIC` | **FAIL** | `scripts/validate_installer_fast.py` tests dynamic port functions with test inputs, but lacks a static code scanner to reject hard-coded runtime URLs (e.g., `http://...:5500`) while allowing `start_port=5500`. |

---

## 2. Detailed Technical Audit

### A. Windows Final Installer Screen (`WINDOWS_FINISHED_PAGE_URL` & `WINDOWS_DYNAMIC_PORT_HANDLING`)

#### Current Implementation Analysis
- **File**: `scripts/hotchords.iss` (Lines 36–60)
  ```pascal
  [Messages]
  FinishedHeadingLabel=HotChords is ready.
  FinishedLabel=Setup has finished installing [name] on your computer.%n%nWhen launched, HotChords starts its local engine and opens automatically in your default browser at:%nhttp://hotchords.localhost:<PORT>%n%nIf HotChords does not open automatically, click Finish with 'Launch HotChords' checked, or open the desktop shortcut.
  ```
- **Execution Mechanism**:
  1. Inno Setup displays the `wpFinished` page **before** launching `HotChords.exe`.
  2. Because `HotChords.exe` has not yet started, the dynamic port selection (`get_free_port(5500)`) has not executed.
  3. Consequently, the Finished Page displays literal text `<PORT>` rather than a resolved port number.
  4. The installer Finished Page does **not** provide a live clickable link to the running application because no running server instance exists at that wizard step.

#### Correct UX Architecture & Limitation
- **Inno Setup Limitation**: An installer wizard cannot know a runtime-selected socket port before the child executable is spawned.
- **Runtime Hand-Off UX**:
  1. The Inno Setup completion page informs the user that HotChords will launch upon clicking **Finish** with "Launch HotChords" selected.
  2. When `HotChords.exe` starts, `backend/main.py` resolves `PORT`, prints the standardized banner with `http://hotchords.localhost:<PORT>`, and calls `webbrowser.open(f"http://hotchords.localhost:{PORT}")`.
  3. If browser auto-launch fails, the runtime exposes the URL via standard console output and/or a local runtime state file.

---

### B. macOS Clean-Machine Runtime (`MACOS_SELF_CONTAINED` & `MACOS_SYSTEM_PYTHON_DEPENDENCY`)

#### Current Implementation Analysis
- **File**: `scripts/build_macos_dmg.sh` (Lines 20–73)
  ```bash
  # 1. Source Copying (No PyInstaller / Standalone Python Bundle)
  cp -R "${PROJECT_ROOT}/backend" "${APP_BUNDLE}/Contents/Resources/"
  cp -R "${PROJECT_ROOT}/frontend" "${APP_BUNDLE}/Contents/Resources/"
  cp -R "${PROJECT_ROOT}/test songs" "${APP_BUNDLE}/Contents/Resources/"
  cp "${PROJECT_ROOT}/hotchords.py" "${APP_BUNDLE}/Contents/Resources/"
  cp "${PROJECT_ROOT}/requirements.txt" "${APP_BUNDLE}/Contents/Resources/"

  # 2. Launcher Script
  cat << 'EOF' > "${APP_BUNDLE}/Contents/MacOS/HotChords"
  #!/usr/bin/env bash
  RESOURCE_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
  cd "${RESOURCE_DIR}"

  # Find Python 3
  if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
  elif [ -f "/opt/homebrew/bin/python3" ]; then
      PYTHON_BIN="/opt/homebrew/bin/python3"
  elif [ -f "/usr/local/bin/python3" ]; then
      PYTHON_BIN="/usr/local/bin/python3"
  else
      PYTHON_BIN="python"
  fi

  exec "${PYTHON_BIN}" hotchords.py
  EOF
  ```

#### Failure Root Cause
1. **Host Python Dependency**: The launcher directly invokes `command -v python3`, `/opt/homebrew/bin/python3`, or `/usr/local/bin/python3`.
2. **Missing Dependencies on Clean Mac**: On a clean Apple Silicon Mac without developer tools or Python virtual environments, `HotChords.app` will fail immediately with either `python3 not found` or `ModuleNotFoundError: No module named 'fastapi'` (and `librosa`, `uvicorn`, `soundfile`, `pydantic`).
3. **No Embedded Runtime**: Unlike the Windows build script (`build_windows_installer.ps1`) which uses PyInstaller `--onedir --windowed` with hidden imports and dependency collection, `build_macos_dmg.sh` creates a shallow wrapper around loose Python source files.

---

### C. Fast Validator Port Check (`FAST_VALIDATOR_PORT_LOGIC`)

#### Current Implementation Analysis
- **File**: `scripts/validate_installer_fast.py` (Lines 152–191)
  - Tests `get_app_url()` with synthetic inputs `5507` and `8080`.
  - Verifies that `print_ready_banner()` formats the provided port.

#### Defect / Limitation
- **Missing Static Code Audit**: The validator does not scan codebase files (`backend/`, `hotchords.py`, `scripts/`) to ensure no static strings like `"http://hotchords.localhost:5500"` or `"http://localhost:5500"` are hardcoded in runtime launch routines.
- **Required Distinction**:
  - `ALLOW`: `def get_free_port(start_port=5500)` (Configuration / search start point).
  - `REJECT`: Hardcoded runtime URL references that assume 5500 is guaranteed at runtime.

---

## 3. Findings Summary

1. `WINDOWS_FINISHED_PAGE_URL = FAIL` (Inno Setup Finished Page cannot obtain runtime port before process launch; runtime handoff relies on application auto-opening the browser upon launch).
2. `WINDOWS_DYNAMIC_PORT_HANDLING = PASS` (Runtime properly calculates dynamic port and opens `http://hotchords.localhost:<PORT>`).
3. `MACOS_SELF_CONTAINED = FAIL` (`build_macos_dmg.sh` does not bundle an embedded Python interpreter or dependencies).
4. `MACOS_SYSTEM_PYTHON_DEPENDENCY = YES` (`Contents/MacOS/HotChords` relies on host `python3`).
5. `FAST_VALIDATOR_PORT_LOGIC = FAIL` (`validate_installer_fast.py` lacks a static audit differentiating default search start `5500` from hardcoded runtime URLs).
