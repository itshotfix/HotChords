"""
tests/test_chord_transition_engine.py

Pytest suite executing and validating ChordTransitionEngine scenarios for Phase 6C.
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestChordTransitionEngine(unittest.TestCase):
    """Test suite executing the 16+ ChordTransitionEngine test scenarios."""

    def test_chord_transition_engine_scenarios(self):
        """Runs the node test suite validating all scenarios of ChordTransitionEngine."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_chord_transition_engine.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"ChordTransitionEngine tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All ChordTransitionEngine tests passed successfully!", result.stdout)
