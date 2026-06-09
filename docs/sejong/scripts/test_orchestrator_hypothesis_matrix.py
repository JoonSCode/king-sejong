#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "benchmark_orchestrator_hypothesis_matrix.py"
sys.path.insert(0, str(SEJONG_ROOT / "scripts"))

import benchmark_orchestrator_hypothesis_matrix as matrix  # noqa: E402


class OrchestratorHypothesisMatrixTests(unittest.TestCase):
    def test_builtin_matrix_evaluates_at_least_ten_hypotheses_per_area(self) -> None:
        report = matrix.evaluate(
            matrix.built_in_candidates(),
            matrix.MIN_HYPOTHESES_PER_AREA,
            matrix.MIN_OVERALL_SCORE,
        )

        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["area_count"], 3)
        self.assertGreaterEqual(report["total_hypotheses"], 30)
        self.assertEqual(
            {item["candidate_id"] for item in report["adopted_hypotheses"]},
            {
                "ranked-matrix-with-tie-breakers",
                "lead-owned-bounded-subagents",
                "thin-validation-layer",
            },
        )
        self.assertTrue(report["operational_corpus"]["passed"], report["operational_corpus"]["failures"])
        self.assertEqual(report["operational_corpus"]["case_count"], 6)
        for area in report["area_results"]:
            self.assertGreaterEqual(area["candidate_count"], matrix.MIN_HYPOTHESES_PER_AREA)
            self.assertIsNotNone(area["selected"])
            self.assertTrue(area["selected"]["trial_results"])
            self.assertEqual(area["selected"]["score"], 1.0)

    def test_operational_corpus_refs_exist_and_align_to_selected_candidates(self) -> None:
        report = matrix.evaluate(
            matrix.built_in_candidates(),
            matrix.MIN_HYPOTHESES_PER_AREA,
            matrix.MIN_OVERALL_SCORE,
        )
        corpus = report["operational_corpus"]

        self.assertTrue(corpus["passed"], corpus["failures"])
        for case in corpus["cases"]:
            self.assertTrue(case["passed"], case)
            self.assertEqual(case["missing_refs"], [])
            self.assertEqual(case["missing_capabilities"], [])

    def test_required_areas_and_minimum_hypothesis_count_are_hard_targets(self) -> None:
        too_small = [
            item
            for item in matrix.built_in_candidates()
            if item.area_id != "architecture_refactor_policy"
        ]
        report = matrix.evaluate(too_small, matrix.MIN_HYPOTHESES_PER_AREA, matrix.MIN_OVERALL_SCORE)

        self.assertFalse(report["passed"])
        self.assertIn("missing required improvement area: architecture_refactor_policy", report["failures"])
        strict_report = matrix.evaluate(too_small[:8], matrix.MIN_HYPOTHESES_PER_AREA, matrix.MIN_OVERALL_SCORE)
        self.assertFalse(strict_report["passed"])
        self.assertIn("has 8 hypotheses", "\n".join(strict_report["failures"]))

    def test_tie_breakers_pick_unique_candidate_from_equal_primary_scores(self) -> None:
        base = next(
            item
            for item in matrix.built_in_candidates()
            if item.id == "ranked-matrix-with-tie-breakers"
        )
        stronger_tie = replace(base, id="same-score-stronger-tie")
        weaker_tie = replace(
            base,
            id="same-score-weaker-tie",
            metrics={
                **base.metrics,
                "outcome_quality": 0.9567,
                "observability_diagnosability": base.metrics["observability_diagnosability"] - 0.01,
            },
        )
        # The weighted score rounds to the same primary value, but the ordered
        # tie-break dimensions should still separate the candidates.
        candidates = [stronger_tie, weaker_tie]
        for idx in range(matrix.MIN_HYPOTHESES_PER_AREA - len(candidates)):
            candidates.append(
                replace(
                    base,
                    id=f"filler-{idx}",
                    metrics={
                        **base.metrics,
                        "outcome_quality": 0.80,
                        "observability_diagnosability": 0.85,
                        "reliability_reproducibility": 0.85,
                        "efficiency_cost": 0.55,
                    },
                )
            )

        report = matrix.evaluate_area(
            "hypothesis_selection_gate",
            candidates,
            matrix.MIN_HYPOTHESES_PER_AREA,
            matrix.MIN_OVERALL_SCORE,
        )

        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["selected"]["id"], "same-score-stronger-tie")
        self.assertTrue(report["tie_breakers_used"])
        self.assertEqual(report["unresolved_ties"], [])

    def test_cli_require_targets_outputs_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--json", "--require-targets"],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], matrix.FORMAT)
        self.assertTrue(payload["passed"])
        self.assertGreaterEqual(payload["total_hypotheses"], 30)


if __name__ == "__main__":
    unittest.main()
