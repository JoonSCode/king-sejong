#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
EVALUATOR = SEJONG_ROOT / "scripts" / "outcome_quality_evaluator.py"
FIXTURE_ROOT = SEJONG_ROOT / "examples" / "outcome-evaluation" / "tagback-growth"


def run_evaluator(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EVALUATOR), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class OutcomeQualityEvaluatorTests(unittest.TestCase):
    def test_tagback_candidate_beats_latest_sot_baseline_on_result_quality(self) -> None:
        result = run_evaluator(
            [
                "compare",
                "--task",
                str(FIXTURE_ROOT / "task.json"),
                "--baseline",
                str(FIXTURE_ROOT / "baseline-current-sot.result.json"),
                "--candidate",
                str(FIXTURE_ROOT / "candidate-runtime-contracts.result.json"),
                "--min-delta",
                "0.12",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.outcome-quality-comparison/v0.1-draft")
        self.assertEqual(payload["winner"], "candidate")
        self.assertEqual(payload["recommendation"], "promote_candidate")
        self.assertGreaterEqual(payload["score_delta"], 0.12)
        self.assertIn("causal_diagnosis", payload["dimension_scores"])
        self.assertIn("experiment_prioritization", payload["dimension_scores"])
        self.assertIn("owner_split", payload["dimension_scores"])

    def test_missing_required_dimension_fails_the_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task = {
                "format": "sejong.outcome-quality-task/v0.1-draft",
                "task_id": "minimal",
                "prompt": "Make the app successful.",
                "goal": "Produce a better strategy artifact.",
                "min_promote_delta": 0.1,
                "required_dimensions": [
                    {
                        "id": "causal_diagnosis",
                        "weight": 1.0,
                        "checks": ["root_causes"],
                    }
                ],
            }
            result_doc = {
                "format": "sejong.outcome-quality-result/v0.1-draft",
                "run_id": "bad",
                "label": "candidate",
                "summary": "Shallow plan.",
                "dimensions": {},
            }
            task_path = tmp_path / "task.json"
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")
            baseline_path.write_text(json.dumps(result_doc | {"run_id": "baseline", "label": "baseline"}), encoding="utf-8")
            candidate_path.write_text(json.dumps(result_doc), encoding="utf-8")

            result = run_evaluator(
                [
                    "compare",
                    "--task",
                    str(task_path),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--min-delta",
                    "0.1",
                ]
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required dimension", result.stderr)


if __name__ == "__main__":
    unittest.main()
