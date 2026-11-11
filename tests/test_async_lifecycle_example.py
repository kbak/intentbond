"""Keep the portable example's finite labels, exact regressions and bounds executable."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/async-lifecycle"


class AsyncLifecycleExampleTests(unittest.TestCase):
    def command(self, *args, optimize=False):
        return subprocess.run(
            [sys.executable, "-B", *(["-O"] if optimize else []), str(EXAMPLE / "demo.py"), *args],
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_retained_outcomes_match_both_models_and_reject_wrong_outputs(self):
        # [utest->req~ib-repair-cases~1]
        result = self.command("--references-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["total_cases"], 754)
        self.assertEqual(data["negative_output_controls"], 544)
        self.assertEqual(data["malformed_schedules"], 9)
        self.assertEqual(data["exact_regressions"], 2)
        self.assertTrue(data["semantic_retention_matched"])

    def test_qualification_cannot_silently_disable_its_assertions(self):
        result = self.command("--references-only", optimize=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without -O", result.stderr)

    def test_example_refuses_outputs_inside_its_checkout(self):
        # [utest->req~ib-repair-boundaries~1]
        output = EXAMPLE / "must-not-be-created"
        self.assertFalse(output.exists())
        result = self.command("--out", str(output))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the source checkout", result.stderr)
        self.assertFalse(output.exists())
