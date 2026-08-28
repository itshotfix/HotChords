"""
tests/test_current_chord_engine.py

Pytest suite executing and validating CurrentChordEngine scenarios for Phase 6A.
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestCurrentChordEngine(unittest.TestCase):
    """Test suite executing the 15 CurrentChordEngine test scenarios."""

    def test_current_chord_engine_scenarios(self):
        """Runs the node test suite validating all 15 scenarios of CurrentChordEngine."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_current_chord_engine.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"CurrentChordEngine tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All 15 CurrentChordEngine scenarios passed successfully!", result.stdout)
