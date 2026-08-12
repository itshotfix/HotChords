"""
backend/utils/preflight.py

Lightweight setup verification for HotChords.
Checks the environment and reports human-readable status for each requirement.

Usage:
    python -m backend.utils.preflight

No expensive operations are performed (no audio analysis, no model loading).
"""

import sys
import os
import socket
import importlib

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 12)

REQUIRED_PACKAGES = [
    ("librosa", "Audio analysis (chroma, beats, HPSS)"),
    ("numpy", "Numerical computation"),
    ("scipy", "Signal processing"),
    ("fastapi", "API server"),
    ("uvicorn", "ASGI server"),
    ("pydantic", "Data validation"),
    ("soundfile", "Audio file I/O (WAV, FLAC, MP3)"),
]

OPTIONAL_PACKAGES = [
    ("torch", "PyTorch (required for Demucs AI stem separation)"),
    ("demucs", "AI source separation (optional — analysis works without it)"),
]

DEFAULT_PORT = 5500

# ══════════════════════════════════════════════════════════════
#  CHECK FUNCTIONS
# ══════════════════════════════════════════════════════════════

def check_python_version():
    """Verify Python version is within supported range."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    
    if (v.major, v.minor) < MIN_PYTHON:
        return False, (
            f"Python {version_str} is too old. "
            f"HotChords requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.\n"
            f"  Download from: https://www.python.org/downloads/"
        )
    
    if (v.major, v.minor) > MAX_PYTHON:
        return None, (
            f"Python {version_str} is newer than tested range "
            f"({MIN_PYTHON[0]}.{MIN_PYTHON[1]}-{MAX_PYTHON[0]}.{MAX_PYTHON[1]}). "
            f"It may work, but has not been validated."
        )
    
    return True, f"Python {version_str}"


def check_package(package_name):
    """Try to import a package and return its version if available."""
    try:
        mod = importlib.import_module(package_name)
        version = getattr(mod, "__version__", "installed")
        return True, version
    except ImportError:
        return False, "not installed"
    except Exception as e:
        return False, f"import error: {e}"


def check_ffmpeg():
    """Verify FFmpeg is available via imageio-ffmpeg or system PATH."""
    # Strategy 1: imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(exe):
            return True, f"Bundled via imageio-ffmpeg: {exe}"
    except ImportError:
        pass
    except Exception:
        pass
    
    # Strategy 2: System PATH
    import shutil
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return True, f"System FFmpeg: {system_ffmpeg}"
    
    return False, (
        "FFmpeg not found. Install imageio-ffmpeg:\n"
        "  pip install imageio-ffmpeg>=0.4.9\n"
        "Or install FFmpeg on your system:\n"
        "  macOS:   brew install ffmpeg\n"
        "  Windows: winget install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg"
    )


def check_directories():
    """Verify required project directories exist."""
    # Determine project root: this file is at backend/utils/preflight.py
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    required_dirs = ["frontend", "backend", os.path.join("frontend", "css"), os.path.join("frontend", "js")]
    missing = []
    for d in required_dirs:
        full_path = os.path.join(project_root, d)
        if not os.path.isdir(full_path):
            missing.append(d)
    
    if missing:
        return False, f"Missing directories: {', '.join(missing)}"
    
    # Check for index.html
    index_path = os.path.join(project_root, "frontend", "index.html")
    if not os.path.isfile(index_path):
        return False, "frontend/index.html not found"
    
    return True, f"Project root: {project_root}"


def check_port(port=DEFAULT_PORT):
    """Check if the default port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(("127.0.0.1", port))
        if result != 0:
            return True, f"Port {port} is available"
        else:
            return None, (
                f"Port {port} is already in use. "
                f"HotChords will automatically try the next available port."
            )


# ══════════════════════════════════════════════════════════════
#  RUNNER
# ══════════════════════════════════════════════════════════════

def run_preflight():
    """Run all preflight checks and return results."""
    results = []
    all_ok = True
    
    # Python version
    ok, msg = check_python_version()
    results.append(("Python Version", ok, msg))
    if ok is False:
        all_ok = False
    
    # Required packages
    for pkg, desc in REQUIRED_PACKAGES:
        ok, msg = check_package(pkg)
        results.append((f"{pkg} ({desc})", ok, msg))
        if ok is False:
            all_ok = False
    
    # Optional packages
    for pkg, desc in OPTIONAL_PACKAGES:
        ok, msg = check_package(pkg)
        # Optional packages don't fail the overall check
        results.append((f"{pkg} ({desc})", ok if ok else None, msg))
    
    # FFmpeg
    ok, msg = check_ffmpeg()
    results.append(("FFmpeg", ok, msg))
    if ok is False:
        all_ok = False
    
    # Directories
    ok, msg = check_directories()
    results.append(("Project Structure", ok, msg))
    if ok is False:
        all_ok = False
    
    # Port
    ok, msg = check_port()
    results.append((f"Port {DEFAULT_PORT}", ok, msg))
    
    return all_ok, results


def print_report():
    """Print a human-readable preflight report."""
    print()
    print("=" * 56)
    print("  HotChords — Environment Check")
    print("=" * 56)
    print()
    
    all_ok, results = run_preflight()
    
    for name, ok, msg in results:
        if ok is True:
            icon = "  ✓"
        elif ok is False:
            icon = "  ✗"
        else:
            icon = "  ~"
        
        # For multiline messages, indent continuation lines
        lines = msg.split("\n")
        print(f"{icon}  {name}: {lines[0]}")
        for line in lines[1:]:
            print(f"       {line}")
    
    print()
    if all_ok:
        print("  All checks passed. HotChords is ready to run.")
        print("  Start with: python hotchords.py")
    else:
        print("  Some checks failed. Please resolve the issues above.")
        print("  Re-run this check: python -m backend.utils.preflight")
    
    print()
    return all_ok


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    success = print_report()
    sys.exit(0 if success else 1)
