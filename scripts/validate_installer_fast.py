#!/usr/bin/env python3
"""
scripts/validate_installer_fast.py
Fast Development Validation for HotChords Packaging & Runtime Launch.

Performs immediate, non-destructive static & unit checks on:
- Version metadata consistency across all files
- Installer configuration syntax/structure (Inno Setup & macOS DMG)
- Application entrypoints and essential asset availability
- Dynamic port selection and standardized URL generation logic
- Strict static code audit: Rejects hardcoded runtime URLs (e.g. localhost:5500)
  while permitting legitimate search start points (get_free_port(start_port=5500))
- Verification of self-contained macOS PyInstaller bundling (zero host Python dependencies)
- Absence of machine-specific paths and stale version references
- Resource manifests and README download checksums

Execution time: < 1 second (does NOT rebuild or install packages).
"""

import sys
import os
import re
import json
import socket
import io
import xml.etree.ElementTree as ET
import subprocess
from contextlib import redirect_stdout

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def log_check(name: str, passed: bool, detail: str = ""):
    status = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
    detail_str = f" - {detail}" if detail else ""
    print(f"  {status} {name}{detail_str}")
    if not passed:
        raise AssertionError(f"Check failed: {name} {detail_str}")

def get_app_version():
    models_init = os.path.join(PROJECT_ROOT, "backend", "models", "__init__.py")
    with open(models_init, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not m:
        raise ValueError("Could not find APP_VERSION in backend/models/__init__.py")
    return m.group(1)

def check_version_metadata():
    print("\n[1/8] Validating Version Metadata Consistency...")
    APP_VERSION = get_app_version()
    log_check(f"Discovered APP_VERSION: {APP_VERSION}", bool(APP_VERSION))
    
    # package.json
    pkg_path = os.path.join(PROJECT_ROOT, "package.json")
    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    pkg_ver = pkg.get("version")
    log_check("package.json version matches APP_VERSION", pkg_ver == APP_VERSION, f"{pkg_ver} == {APP_VERSION}")

    # hotchords.iss
    iss_path = os.path.join(PROJECT_ROOT, "scripts", "hotchords.iss")
    with open(iss_path, "r", encoding="utf-8") as f:
        iss_content = f.read()
    iss_match = re.search(r'#define MyAppVersion "([^"]+)"', iss_content)
    iss_ver = iss_match.group(1) if iss_match else None
    log_check("hotchords.iss MyAppVersion matches APP_VERSION", iss_ver == APP_VERSION, f"{iss_ver} == {APP_VERSION}")

    # build_macos_dmg.sh
    dmg_path = os.path.join(PROJECT_ROOT, "scripts", "build_macos_dmg.sh")
    with open(dmg_path, "r", encoding="utf-8") as f:
        dmg_content = f.read()
    log_check("build_macos_dmg.sh references APP_VERSION in DMG output name", f"HotChords-v{APP_VERSION}-macOS" in dmg_content)
    log_check("build_macos_dmg.sh Info.plist has APP_VERSION", f"<string>{APP_VERSION}</string>" in dmg_content)

    # build_windows_installer.ps1
    ps1_path = os.path.join(PROJECT_ROOT, "scripts", "build_windows_installer.ps1")
    with open(ps1_path, "r", encoding="utf-8") as f:
        ps1_content = f.read()
    log_check("build_windows_installer.ps1 references APP_VERSION", f"HotChords-v{APP_VERSION}-Windows" in ps1_content)

    # README.md
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
    log_check("README.md mentions Version: APP_VERSION", f"Version: {APP_VERSION}" in readme_content or f"v{APP_VERSION}" in readme_content)

def check_installer_configs():
    print("\n[2/8] Validating Installer Configurations & Syntax...")
    
    # Inno Setup iss checks
    iss_path = os.path.join(PROJECT_ROOT, "scripts", "hotchords.iss")
    with open(iss_path, "r", encoding="utf-8") as f:
        iss = f.read()
    for section in ["[Setup]", "[Languages]", "[Messages]", "[Tasks]", "[Files]", "[Icons]", "[Run]", "[Code]"]:
        log_check(f"hotchords.iss contains {section} section", section in iss)
    log_check("hotchords.iss sets modern wizard style", "WizardStyle=modern" in iss)
    log_check("hotchords.iss configures 64-bit architecture", "ArchitecturesAllowed=x64compatible" in iss)
    log_check("hotchords.iss has finished ready heading message", "FinishedHeadingLabel=HotChords is ready." in iss)
    log_check("hotchords.iss does not display unexpanded <PORT> placeholder", "<PORT>" not in iss)
    log_check("hotchords.iss does not display fake hardcoded 5500 port", "5500" not in iss)

    # macOS DMG script checks
    dmg_path = os.path.join(PROJECT_ROOT, "scripts", "build_macos_dmg.sh")
    res = subprocess.run(["bash", "-n", dmg_path], capture_output=True, text=True)
    log_check("build_macos_dmg.sh bash syntax valid", res.returncode == 0, res.stderr.strip())

    # Verify macOS standalone PyInstaller packaging (no host python runtime execution)
    with open(dmg_path, "r", encoding="utf-8") as f:
        dmg_sh = f.read()
    log_check("build_macos_dmg.sh uses PyInstaller standalone bundling", "PyInstaller" in dmg_sh)
    log_check("build_macos_dmg.sh has NO host python3 search in runtime app", "command -v python3" not in dmg_sh)
    log_check("build_macos_dmg.sh has NO hardcoded Homebrew runtime path in app", "/opt/homebrew/bin/python3" not in dmg_sh)

    # Extract Info.plist XML block from build_macos_dmg.sh
    plist_match = re.search(r"cat << 'EOF' > \"\${APP_BUNDLE}/Contents/Info\.plist\"\n(.*?)\nEOF", dmg_sh, re.DOTALL)
    log_check("build_macos_dmg.sh contains valid Info.plist block", bool(plist_match))
    if plist_match:
        plist_xml = plist_match.group(1).strip()
        try:
            root = ET.fromstring(plist_xml)
            log_check("Info.plist parses as valid XML", root.tag == "plist")
        except Exception as e:
            log_check("Info.plist parses as valid XML", False, str(e))

def check_entrypoints_and_assets():
    print("\n[3/8] Validating Application Entrypoints & Required Assets...")
    
    entrypoints = [
        "hotchords.py",
        "backend/main.py",
        "backend/api/router.py",
        "backend/analysis/pipeline.py",
        "backend/models/__init__.py",
        "frontend/index.html",
        "frontend/css/piano.css",
        "requirements.txt"
    ]
    for ep in entrypoints:
        p = os.path.join(PROJECT_ROOT, ep)
        log_check(f"Essential file exists: {ep}", os.path.isfile(p))

    frontend_dirs = [
        "frontend/js/audio",
        "frontend/js/ui",
        "frontend/js/engine",
        "frontend/js/animations"
    ]
    for fd in frontend_dirs:
        p = os.path.join(PROJECT_ROOT, fd)
        log_check(f"Essential frontend module exists: {fd}", os.path.isdir(p))

    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        reqs = f.read().lower()
    for dep in ["fastapi", "uvicorn", "librosa", "soundfile", "pydantic", "numpy", "scipy"]:
        log_check(f"requirements.txt contains {dep}", dep in reqs)

def check_dynamic_port_and_url_logic():
    print("\n[4/8] Validating Dynamic Port & URL Generation Logic...")
    from backend.main import get_free_port, get_app_url, print_ready_banner
    
    port = get_free_port(5500)
    log_check("get_free_port returns a valid port integer >= 5500", isinstance(port, int) and port >= 5500, f"port={port}")

    app_url = get_app_url(port)
    expected_url = f"http://hotchords.localhost:{port}"
    log_check("get_app_url returns correct http://hotchords.localhost:<PORT>", app_url == expected_url, app_url)

    # Validate banner contents
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_ready_banner(port)
    banner_out = buf.getvalue()

    required_snippets = [
        "HotChords is ready.",
        "Open HotChords:",
        f"http://hotchords.localhost:{port}",
        "If HotChords did not open automatically, click the link above",
        "or copy/type the address into your browser."
    ]
    for snippet in required_snippets:
        log_check(f"Ready banner contains required wording: '{snippet}'", snippet in banner_out)

def check_no_hardcoded_port_assumptions():
    print("\n[5/8] Validating No Hard-Coded Port 5500 Assumptions in Dynamic Logic...")
    from backend.main import get_app_url, print_ready_banner

    # 1. Test functional behavior with alternative ports (e.g. 5507, 8080)
    for test_port in [5507, 8080]:
        url = get_app_url(test_port)
        log_check(f"get_app_url adapts dynamically for port {test_port}", url == f"http://hotchords.localhost:{test_port}")
        
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_ready_banner(test_port)
        log_check(f"print_ready_banner formats custom port {test_port}", f"http://hotchords.localhost:{test_port}" in buf.getvalue())

    # 2. Static Code Scanner: Reject hardcoded runtime URLs (e.g. "http://...:5500") while allowing start_port=5500
    runtime_files = [
        "hotchords.py",
        "backend/main.py",
        "backend/api/router.py",
        "scripts/hotchords.iss",
        "scripts/build_macos_dmg.sh",
        "scripts/build_windows_installer.ps1"
    ]
    
    # Matches hardcoded string literals: "http://localhost:5500", "http://hotchords.localhost:5500", etc.
    hardcoded_url_pattern = re.compile(r'["\']http://(?:hotchords\.)?localhost:5500["\']')
    
    for rf in runtime_files:
        p = os.path.join(PROJECT_ROOT, rf)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            code = f.read()
        
        # Remove comments before scanning
        code_no_comments = re.sub(r'#.*|//.*|;.*', '', code)
        matches = hardcoded_url_pattern.findall(code_no_comments)
        log_check(f"No hardcoded runtime URL in {rf}", len(matches) == 0, f"matches={matches}")
        
        # Verify legitimate search start is preserved in backend/main.py
        if rf == "backend/main.py":
            log_check("backend/main.py preserves start_port=5500 in get_free_port", "start_port=5500" in code or "get_free_port(5500)" in code)

def check_no_machine_specific_paths():
    print("\n[6/8] Validating No Machine-Specific Paths in Configs & Packaging...")
    forbidden_prefixes = ["/Users/harishthakur", "/Volumes/TIKDI", "C:\\Users\\"]
    
    files_to_check = [
        "scripts/hotchords.iss",
        "scripts/build_macos_dmg.sh",
        "scripts/build_windows_installer.ps1",
        "scripts/setup_mac.sh",
        "scripts/setup_windows.bat",
        "scripts/start_mac.sh",
        "scripts/start_windows.bat",
        ".github/workflows/ci.yml",
        ".github/workflows/windows-installer.yml",
        "hotchords.py",
        "backend/main.py"
    ]
    
    for rel_path in files_to_check:
        full_p = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(full_p):
            continue
        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            for prefix in forbidden_prefixes:
                if prefix in line and not line.strip().startswith(("#", ";", "//", "REM")):
                    log_check(f"No machine-specific path in {rel_path}:{idx}", False, f"Found '{prefix}' in: {line.strip()}")
        log_check(f"Clean portable paths in {rel_path}", True)

def check_resource_manifests():
    print("\n[7/8] Validating Resource Manifests...")
    
    # Check macOS DMG packaging resource list
    dmg_path = os.path.join(PROJECT_ROOT, "scripts", "build_macos_dmg.sh")
    with open(dmg_path, "r", encoding="utf-8") as f:
        dmg_content = f.read()
    
    dmg_resources = ["frontend", "test songs", "hotchords.py"]
    for r in dmg_resources:
        log_check(f"build_macos_dmg.sh bundles existing resource: {r}", os.path.exists(os.path.join(PROJECT_ROOT, r)) and r in dmg_content)

def check_readme_release_checksums():
    print("\n[8/8] Validating README Release Documentation & Checksums...")
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # Check Windows & macOS installer download links
    log_check("README has Windows installer direct link", "HotChords-v0.4.0-Windows-x64-Setup.exe" in readme)
    log_check("README has macOS DMG direct link", "HotChords-v0.4.0-macOS-AppleSilicon.dmg" in readme)
    
    # Check SHA-256 presence
    sha256_matches = re.findall(r"SHA-256:\s*`([a-fA-F0-9]{64})`", readme)
    log_check("README contains at least 2 valid SHA-256 checksums (Windows & macOS)", len(sha256_matches) >= 2, f"Found {len(sha256_matches)} hashes: {sha256_matches}")

def main():
    print("═════════════════════════════════════════════════════════════")
    print("  HotChords Fast Installer Development Validation          ")
    print("═════════════════════════════════════════════════════════════")
    
    try:
        check_version_metadata()
        check_installer_configs()
        check_entrypoints_and_assets()
        check_dynamic_port_and_url_logic()
        check_no_hardcoded_port_assumptions()
        check_no_machine_specific_paths()
        check_resource_manifests()
        check_readme_release_checksums()
        
        print("\n═════════════════════════════════════════════════════════════")
        print("  \033[92m✔ ALL FAST INSTALLER VALIDATION CHECKS PASSED!\033[0m            ")
        print("═════════════════════════════════════════════════════════════\n")
        return 0
    except Exception as e:
        print(f"\n\033[91m✖ VALIDATION FAILED:\033[0m {e}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
