#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "benchmark_workflow_run.py"


class WorkflowRunBenchmarkTests(unittest.TestCase):
    def test_benchmark_matrix_and_performance_pass(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--worker-count",
                "200",
                "--evidence-count",
                "400",
                "--max-seconds",
                "1.0",
                "--json",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["passed"])
        self.assertEqual(len(data["cases"]), 18)
        case_ids = {case["id"] for case in data["cases"]}
        self.assertIn("promotion-without-approval", case_ids)
        self.assertIn("weak-positive-delta-promotion", case_ids)
        self.assertIn("empty-acceptance-criteria", case_ids)
        self.assertIn("final-recommendation-mismatch", case_ids)
        self.assertIn("weak-other-provenance", case_ids)
        self.assertIn("manual-shadow-promoted", case_ids)
        self.assertTrue(data["performance"]["passed"])


if __name__ == "__main__":
    unittest.main()
