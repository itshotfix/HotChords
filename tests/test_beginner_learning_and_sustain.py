"""
tests/test_beginner_learning_and_sustain.py

Pytest suite executing and validating Phase 7B: Beginner Learning Hand Animation & Sustain Pedal.
"""

import subprocess
import os
import unittest


class TestBeginnerLearningAndSustain(unittest.TestCase):
    """Test suite executing Beginner Learning HUD and Sustain test scenarios."""

    def test_beginner_learning_and_sustain_scenarios(self):
        """Runs the node test suite validating static chart, live HUD, hand animation, and sustain pedal."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_beginner_learning_and_sustain.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Beginner Learning & Sustain tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All Beginner Learning & Sustain tests passed successfully!", result.stdout)


if __name__ == "__main__":
    unittest.main()
