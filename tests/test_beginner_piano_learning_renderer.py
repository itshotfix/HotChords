"""
tests/test_beginner_piano_learning_renderer.py

Pytest suite executing and validating BeginnerPianoLearningRenderer scenarios for Phase 6D-1.
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestBeginnerPianoLearningRenderer(unittest.TestCase):
    """Test suite executing the 15+ BeginnerPianoLearningRenderer test scenarios."""

    def test_beginner_piano_learning_renderer_scenarios(self):
        """Runs the node test suite validating all scenarios of BeginnerPianoLearningRenderer."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_beginner_piano_learning_renderer.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"BeginnerPianoLearningRenderer tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All BeginnerPianoLearningRenderer tests passed successfully!", result.stdout)
