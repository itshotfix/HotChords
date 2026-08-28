"""
tests/test_piano_fingering_engine.py

Pytest suite executing and validating PianoFingeringEngine scenarios for Phase 6B.
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestPianoFingeringEngine(unittest.TestCase):
    """Test suite executing the 15+ PianoFingeringEngine test scenarios."""

    def test_piano_fingering_engine_scenarios(self):
        """Runs the node test suite validating all scenarios of PianoFingeringEngine."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_piano_fingering_engine.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"PianoFingeringEngine tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All PianoFingeringEngine tests passed successfully!", result.stdout)
