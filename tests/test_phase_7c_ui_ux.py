"""
tests/test_phase_7c_ui_ux.py
Pytest runner for HotChords Phase 7C UI/UX & Playback Experience Test Suite.
"""

import subprocess
import os
import pytest

class TestPhase7CUIUX:
    def test_phase_7c_ui_ux_scenarios(self):
        """Execute the Phase 7C Node.js unit and integration test suite."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_phase_7c_ui_ux.js")
        
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True
        )
        
        print("\n--- Phase 7C JS Test Runner Output ---")
        print(result.stdout)
        if result.stderr:
            print("--- Stderr ---")
            print(result.stderr)
            
        assert result.returncode == 0, f"Phase 7C JS test suite failed with exit code {result.returncode}:\n{result.stderr}"
        assert "All 20/20 HotChords Phase 7C tests PASSED successfully!" in result.stdout
