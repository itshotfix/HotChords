"""
tests/test_beginner_chart_integration.py

Pytest suite executing and validating Beginner Chart + Piano Learning Integration for Phase 6D-2.
Executes the dedicated Node.js test runner to ensure 100% deterministic test execution.
"""

import subprocess
import os
import unittest


class TestBeginnerChartIntegration(unittest.TestCase):
    """Test suite executing the 16+ Beginner Chart Integration test scenarios."""

    def test_beginner_chart_integration_scenarios(self):
        """Runs the node test suite validating all scenarios of Beginner Chart Integration."""
        test_js_path = os.path.join(os.path.dirname(__file__), "test_beginner_chart_integration.js")
        result = subprocess.run(
            ["node", test_js_path],
            capture_output=True,
            text=True,
            check=False
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Beginner Chart Integration tests failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        self.assertIn("All Beginner Chart Integration tests passed successfully!", result.stdout)
