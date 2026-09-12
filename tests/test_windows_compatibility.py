"""
tests/test_windows_compatibility.py

Automated tests for Windows platform compatibility:
1. Verifies preflight report generates ASCII-safe output without Unicode encoding errors.
2. Verifies frontend_dir resolution in backend/api/router.py.
3. Verifies audioop availability on the active Python runtime.
"""

import sys
import io
import os
import pytest
from backend.utils.preflight import run_preflight, print_report
from backend.api.router import _get_frontend_dir


def test_preflight_ascii_safe_output():
    """Verify print_report encodes cleanly in cp1252 (Windows default code page)."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        success = print_report()
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # Verify that the output can be encoded cleanly into Windows-1252
    encoded_cp1252 = output.encode("cp1252")
    assert len(encoded_cp1252) > 0

    # Verify no non-ASCII unicode symbols exist in status indicators
    assert "[OK]" in output or "[FAIL]" in output or "[INFO]" in output
    assert "✓" not in output
    assert "✗" not in output


def test_frontend_dir_resolution():
    """Verify frontend directory resolves to a valid existing path."""
    fdir = _get_frontend_dir()
    assert os.path.isdir(fdir)
    assert os.path.isfile(os.path.join(fdir, "index.html"))
    assert os.path.isdir(os.path.join(fdir, "css"))
    assert os.path.isdir(os.path.join(fdir, "js"))


def test_audioop_available_on_runtime():
    """Verify audioop is available either via standard library or audioop-lts."""
    try:
        import audioop
        assert audioop is not None
    except ImportError:
        import pyaudioop as audioop
        assert audioop is not None
