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
RUNNER = SEJONG_ROOT / "scripts" / "benchmark_workflow_run_comparison.py"
sys.path.insert(0, str(SEJONG_ROOT / "scripts"))
import benchmark_workflow_run_comparison as comparison_benchmark  # noqa: E402
from sejong_workflow_run import run_failures  # noqa: E402


class WorkflowRunComparisonBenchmarkTests(unittest.TestCase):
    def test_hardened_workflow_run_beats_legacy_by_ten_percent(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--worker-count",
                "200",
                "--evidence-count",
                "400",
                "--min-score-delta",
                "0.10",
                "--min-multi-metric-score",
                "0.90",
                "--max-large-ledger-seconds",
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
        self.assertGreaterEqual(data["score_delta"], 0.10)
        self.assertEqual(data["candidate"]["average_score"], 1.0)
        self.assertGreater(data["candidate"]["average_score"], data["baseline"]["average_score"])
        self.assertGreater(data["multi_metric_delta"], 0)
        self.assertGreaterEqual(data["candidate_multi_metric"]["overall_score"], 0.90)
        self.assertEqual(data["candidate_multi_metric"]["hard_gate_failures"], [])
        self.assertEqual(
            set(data["candidate_multi_metric"]["dimensions"]),
            set(comparison_benchmark.DIMENSION_WEIGHTS),
        )
        self.assertEqual(
            set(data["candidate_multi_metric"]["dimension_minimums"]),
            set(comparison_benchmark.DIMENSION_MINIMUMS),
        )
        for dimension, minimum in data["candidate_multi_metric"]["dimension_minimums"].items():
            self.assertGreaterEqual(data["candidate_multi_metric"]["dimensions"][dimension]["score"], minimum)
        promotion_metrics = data["candidate_multi_metric"]["dimensions"]["promotion_decision_quality"]["metrics"]
        self.assertEqual(promotion_metrics["critical_miss_rate"], 0.0)
        outcome_metrics = data["candidate_multi_metric"]["dimensions"]["outcome_quality"]["metrics"]
        self.assertEqual(outcome_metrics["weak_positive_delta_gate_score"], 1.0)
        self.assertEqual(outcome_metrics["acceptance_criteria_gate_score"], 1.0)
        self.assertEqual(outcome_metrics["final_recommendation_match_gate_score"], 1.0)
        efficiency_metrics = data["candidate_multi_metric"]["dimensions"]["efficiency_cost"]["metrics"]
        self.assertEqual(efficiency_metrics["large_ledger_threshold_seconds"], 1.0)
        self.assertTrue(data["performance"]["passed"])

    def test_strict_multi_metric_threshold_fails_cleanly(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--worker-count",
                "50",
                "--evidence-count",
                "100",
                "--min-score-delta",
                "0.10",
                "--min-multi-metric-score",
                "1.01",
                "--json",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertFalse(data["passed"])
        self.assertLess(data["candidate_multi_metric"]["overall_score"], 1.01)

    def test_missing_required_matrix_case_is_reported_not_crashed(self) -> None:
        cases = comparison_benchmark.curated_cases()
        evaluation = comparison_benchmark.evaluate_validator(
            "hardened_workflow_run_validation",
            run_failures,
            cases,
        )
        evaluation["results"] = [item for item in evaluation["results"] if item["id"] != "missing-metrics"]
        perf = comparison_benchmark.performance_comparison(20, 40, 1.0)

        scorecard = comparison_benchmark.multi_metric_scorecard(
            evaluation,
            cases,
            run_failures,
            perf,
            1.0,
        )

        self.assertIn("missing required matrix case: missing-metrics", scorecard["hard_gate_failures"])


if __name__ == "__main__":
    unittest.main()
