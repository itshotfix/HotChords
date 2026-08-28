"""
tests/test_workspace_hands_and_timeline.py
Python test wrapper for HotChords Hands and Timeline verification test suite.
"""

import os
import subprocess
import unittest

class TestWorkspaceHandsAndTimeline(unittest.TestCase):

    def test_workspace_hands_and_timeline_scenarios(self):
        """Run Node.js test suite verifying lyrics removal, hands across all modes, and lag-free timeline."""
        js_test_path = os.path.join(
            os.path.dirname(__file__), "test_workspace_hands_and_timeline.js"
        )
        self.assertTrue(
            os.path.isfile(js_test_path), f"JS test file missing: {js_test_path}"
        )

        result = subprocess.run(
            ["node", js_test_path],
            capture_output=True,
            text=True,
            check=False
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        self.assertEqual(
            result.returncode, 0, f"JS test suite failed:\n{result.stderr}\n{result.stdout}"
        )

if __name__ == "__main__":
    unittest.main()
