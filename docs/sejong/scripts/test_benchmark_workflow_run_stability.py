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
RUNNER = SEJONG_ROOT / "scripts" / "benchmark_workflow_run_stability.py"


class WorkflowRunStabilityBenchmarkTests(unittest.TestCase):
    def test_stability_benchmark_passes_with_repeated_large_ledger_samples(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--samples",
                "3",
                "--warmups",
                "1",
                "--worker-count",
                "50",
                "--evidence-count",
                "100",
                "--max-large-ledger-seconds",
                "1.0",
                "--max-p95-seconds",
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
        self.assertEqual(data["sample_count"], 3)
        self.assertLessEqual(data["candidate_elapsed_seconds"]["p95"], 1.0)

    def test_stability_benchmark_fails_when_threshold_is_impossible(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--samples",
                "2",
                "--warmups",
                "0",
                "--worker-count",
                "50",
                "--evidence-count",
                "100",
                "--max-large-ledger-seconds",
                "0.0",
                "--max-p95-seconds",
                "0.0",
                "--json",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertFalse(data["passed"])
        self.assertGreater(data["candidate_elapsed_seconds"]["p95"], 0.0)


if __name__ == "__main__":
    unittest.main()
