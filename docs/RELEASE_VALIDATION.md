# HotChords — Installer & Release Validation Policy

This document defines the formal two-tier validation policy for HotChords packaging, installer creation, runtime launching, and release distribution.

---

## 1. Executive Summary & Policy Architecture

Building, packaging, installing, launching, and uninstallation across macOS and Windows operating systems are expensive end-to-end operations. To maintain developer velocity while guaranteeing zero-defect public releases, HotChords enforces a **Two-Tier Validation Gate**:

```
                                  HOTCHORDS CODEBASE
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
        [TIER 1: FAST VALIDATION]                     [TIER 2: RELEASE GATE]
       Executed Routinely on every PR /            Executed ONLY when building &
             Commit / Local Dev                      publishing Release Candidates
                   │                                             │
      • Duration: < 2 Seconds                       • Duration: ~10-15 Minutes
      • No full VM or installer builds              • Real Windows & macOS VMs / Runners
      • Static & unit invariant checks              • Full Install ➔ Launch ➔ Browser ➔ Health ➔ Uninstall
                   │                                             │
                   ▼                                             ▼
          PASS: Code is safe for                        PASS: Approved for Public
          continued development                         Release Publication
```

---

## 2. Tier 1: Fast Development Validation (Routine)

**Execution Rule**: Run routinely during active development, refactoring, documentation updates, and CI automated test runs (`pytest`).

### Objectives
Fast development validation verifies that all packaging configurations, dynamic URL mechanisms, version tags, entrypoint integrity, and static resource manifests remain 100% valid **without** incurring the time cost of PyInstaller compiles, Inno Setup generation, or DMG imaging.

### Validation Matrix
1. **Version Metadata Consistency**:
   - `backend/models/__init__.py` (`APP_VERSION`)
   - `package.json` (`version`)
   - `scripts/hotchords.iss` (`MyAppVersion`)
   - `scripts/build_macos_dmg.sh` (`CFBundleShortVersionString`, `CFBundleVersion`, DMG output name)
   - `scripts/build_windows_installer.ps1` (Output executable version naming)
   - `README.md` (`Version: X.Y.Z` and direct download tags)
2. **Installer Configuration Syntax & Structure**:
   - Inno Setup (`scripts/hotchords.iss`): Verifies required sections (`[Setup]`, `[Languages]`, `[Messages]`, `[Tasks]`, `[Files]`, `[Icons]`, `[Run]`, `[Code]`), 64-bit architecture constraint (`ArchitecturesAllowed=x64compatible`), and modern wizard style.
   - macOS DMG (`scripts/build_macos_dmg.sh`): Bash syntax verification (`bash -n`) and `Info.plist` XML validity.
3. **Application Entrypoints & Required Assets**:
   - Verification of `hotchords.py`, `backend/main.py`, `backend/api/router.py`, `frontend/index.html`, `frontend/css/piano.css`, and core frontend modules.
   - Required dependency verification in `requirements.txt`.
4. **Standardized Runtime URL & Dynamic Port Logic**:
   - Dynamic port selection starting at 5500 via `get_free_port()`.
   - Canonical application URL generation format: `http://hotchords.localhost:<PORT>`.
   - Exact compliance of the ready banner:
     ```
     HotChords is ready.

     Open HotChords:
     http://hotchords.localhost:<PORT>

     If HotChords did not open automatically, click the link above
     or copy/type the address into your browser.
     ```
   - Zero hard-coded assumptions of port 5500.
5. **No Machine-Specific Paths**:
   - Verifies absence of local developer paths (e.g., `/Users/`, `/Volumes/`, `C:\Users\`).
6. **Release Checksum Integrity**:
   - Verifies valid 64-character SHA-256 hashes are documented in `README.md` for both Windows and macOS distributions.

### How to Run Fast Validation
```bash
# Direct execution (runs in ~0.5 seconds)
python3 scripts/validate_installer_fast.py

# Or via pytest test suite
pytest tests/test_installer_validation_fast.py
```

---

## 3. Tier 2: Full Installer Release Validation (Release Gate Only)

**Execution Rule**: Run ONLY when preparing, building, or signing an official public release candidate, or when installer scripts (`scripts/hotchords.iss`, `scripts/build_windows_installer.ps1`, `scripts/build_macos_dmg.sh`) or native launcher code have been modified.

### Objectives
Executes full real-world installation, execution, socket binding, default browser launch, health check verification, and clean uninstallation in clean sandbox environments (Windows 10/11 x64 and macOS Apple Silicon).

### Windows Release Validation Flow
1. **Clean Packaging**:
   - Run PyInstaller standalone directory compilation (`--onedir --windowed`).
   - Run Inno Setup Compiler (`ISCC.exe scripts/hotchords.iss`) to build `HotChords-v<VERSION>-Windows-x64-Setup.exe`.
2. **Silent / UI Installation**:
   - Execute installer in clean target environment (`/VERYSILENT /NORESTART /DIR=...`).
3. **Application Launch & Health Check**:
   - Launch installed `HotChords.exe`.
   - Poll `http://127.0.0.1:<PORT>/health` until HTTP 200 `{"status": "ready"}` is returned.
4. **Browser & Final Screen URL Validation**:
   - Confirm default browser is directed to `http://hotchords.localhost:<PORT>`.
   - Confirm manually opening `http://hotchords.localhost:<PORT>` loads HotChords workstation.
5. **Uninstallation**:
   - Execute uninstaller (`unins000.exe /VERYSILENT`).
   - Confirm application directory and shortcuts are cleanly removed.

### macOS Release Validation Flow
1. **Clean Packaging**:
   - Assemble `HotChords.app` bundle with `Contents/MacOS/HotChords`, `Contents/Info.plist`, and `Contents/Resources`.
   - Run `hdiutil create` to generate `HotChords-v<VERSION>-macOS-AppleSilicon.dmg`.
2. **DMG Mount & Installation**:
   - Mount DMG (`hdiutil attach`).
   - Copy `HotChords.app` to `/Applications/`.
3. **Application Launch & Health Check**:
   - Launch `open -a /Applications/HotChords.app`.
   - Poll `http://127.0.0.1:<PORT>/health` until HTTP 200 is returned.
4. **Browser & URL Notification**:
   - Confirm browser opens `http://hotchords.localhost:<PORT>`.
   - Confirm system notification displays `HotChords is ready` with clickable address.
5. **Cleanup**:
   - Terminate process, unmount DMG, and remove `HotChords.app`.

---

## 4. Re-Validation Triggers & Policy Enforcement

| Change Type | Fast Validation | Full Installer Release Gate |
| :--- | :--- | :--- |
| **Frontend HTML/CSS/JS tweaks** | Required | Not required (Fast validation sufficient) |
| **Backend music theory / ML algorithms** | Required | Not required (Fast validation sufficient) |
| **Documentation / README updates** | Required | Not required (Fast validation sufficient) |
| **Installer script changes (`.iss`, `.ps1`, `.sh`)** | Required | **MANDATORY** before release |
| **Launcher / Server port binding changes** | Required | **MANDATORY** before release |
| **Release Candidate Tagging (e.g. `v0.5.0`)** | Required | **MANDATORY** before publishing |

> [!IMPORTANT]
> Never bypass Tier 2 for an official release candidate. The purpose of Tier 1 is to maximize developer iteration speed during routine coding, while Tier 2 guarantees complete production reliability.
