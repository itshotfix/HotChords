"""
tests/test_phase_8_rearchitecture.py
Pytest runner for HotChords Phase 8 UI/UX Rearchitecture & Responsive Layout Test Suite.
"""

import subprocess
import os
import pytest

class TestPhase8Rearchitecture:
    def test_phase_8_rearchitecture_scenarios(self):
        """Execute the Phase 8 Node.js unit and integration test suite."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_phase_8_rearchitecture.js")
        
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True
        )
        
        print("\n--- Phase 8 JS Test Runner Output ---")
        print(result.stdout)
        if result.stderr:
            print("--- Stderr ---")
            print(result.stderr)
            
        assert result.returncode == 0, f"Phase 8 JS test suite failed with exit code {result.returncode}:\n{result.stderr}"
        assert "HotChords Phase 8 tests PASSED successfully!" in result.stdout
