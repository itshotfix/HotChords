"""
tests/test_installer_validation_fast.py
Automated Pytest wrapper for Fast Installer & Runtime Packaging Validation.
Ensures static packaging checks, dynamic URL generation, and version metadata
are checked routinely without executing full multi-minute installer builds.
"""

import subprocess
import sys
import os
import pytest

def test_fast_installer_validation():
    script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "validate_installer_fast.py")
    res = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Fast installer validation failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
