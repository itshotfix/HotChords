"""
tests/test_playback_lifecycle.py

Pytest suite executing and validating Playback Lifecycle (Stop/Pause/Restart/Mutual Exclusivity).
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestPlaybackLifecycle(unittest.TestCase):
    """Test suite executing playback stop/pause/restart scenarios."""

    def test_playback_lifecycle_scenarios(self):
        """Runs the node test suite validating PLAY -> STOP -> PLAY, PAUSE, RESTART, and Mutual Exclusivity."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_playback_lifecycle.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Playback Lifecycle tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All Playback Lifecycle tests passed successfully!", result.stdout)


if __name__ == "__main__":
    unittest.main()
