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
GATE = SEJONG_ROOT / "scripts" / "blind_semantic_quality_gate.py"


def write_result(path: Path, run_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "format": "sejong.outcome-quality-result/v0.1-draft",
                "run_id": run_id,
                "label": run_id,
                "summary": "fixture",
                "dimensions": {
                    "goal_alignment": {
                        "user_goal_restated": "fixture",
                        "non_goals": "fixture",
                        "acceptance_criteria": "fixture",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def write_task(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "format": "sejong.outcome-quality-task/v0.1-draft",
                "task_id": "blind-fixture",
                "prompt": "Create a report.",
                "goal": "Compare baseline and candidate report quality for the long-session experiment.",
                "min_promote_delta": 0.2,
                "artifact_contract": {
                    "required_paths": ["report.md"],
                    "forbidden_paths": [],
                    "required_checks": ["expected_paths"],
                },
                "required_dimensions": [
                    {
                        "id": "goal_alignment",
                        "weight": 1.0,
                        "checks": ["user_goal_restated"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class BlindSemanticQualityGateTests(unittest.TestCase):
    def test_pack_hides_baseline_candidate_labels_and_writes_key_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_root = root / "baseline"
            candidate_root = root / "candidate"
            baseline_root.mkdir()
            candidate_root.mkdir()
            (baseline_root / "report.md").write_text("short report\n", encoding="utf-8")
            (candidate_root / "report.md").write_text("better report\n", encoding="utf-8")
            task_path = root / "task.json"
            baseline_result = root / "baseline.result.json"
            candidate_result = root / "candidate.result.json"
            packet_path = root / "packet.json"
            key_path = root / "key.json"
            write_task(task_path)
            write_result(baseline_result, "baseline-run")
            write_result(candidate_result, "candidate-run")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "pack",
                    "--task",
                    str(task_path),
                    "--baseline-result",
                    str(baseline_result),
                    "--candidate-result",
                    str(candidate_result),
                    "--baseline-root",
                    str(baseline_root),
                    "--candidate-root",
                    str(candidate_root),
                    "--seed",
                    "fixed",
                    "--write-packet",
                    str(packet_path),
                    "--write-key",
                    str(key_path),
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            key = json.loads(key_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["format"], "sejong.blind-semantic-packet/v0.1-draft")
            self.assertEqual(key["format"], "sejong.blind-semantic-key/v0.1-draft")
            self.assertEqual({item["id"] for item in packet["outputs"]}, {"A", "B"})
            self.assertNotIn("baseline-run", json.dumps(packet))
            self.assertNotIn("candidate-run", json.dumps(packet))
            self.assertNotIn("baseline", json.dumps(packet).lower())
            self.assertNotIn("candidate", json.dumps(packet).lower())
            self.assertNotIn("long-session", json.dumps(packet).lower())
            self.assertEqual(packet["goal"], "Create a report.")
            self.assertEqual(set(key["mapping"].values()), {"baseline", "candidate"})

    def test_judge_result_promotes_candidate_when_blind_score_delta_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet_path = root / "packet.json"
            key_path = root / "key.json"
            judgment_path = root / "judgment.json"
            packet_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.blind-semantic-packet/v0.1-draft",
                        "packet_id": "blind-abc",
                        "generated_at": "2026-05-27T00:00:00Z",
                        "task_id": "blind-fixture",
                        "prompt": "fixture",
                        "goal": "fixture",
                        "rubric": ["goal_fit"],
                        "artifact_paths": ["report.md"],
                        "outputs": [{"id": "A", "artifacts": {}}, {"id": "B", "artifacts": {}}],
                        "judge_instructions": ["fixture"],
                    }
                ),
                encoding="utf-8",
            )
            key_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.blind-semantic-key/v0.1-draft",
                        "packet_id": "blind-abc",
                        "generated_at": "2026-05-27T00:00:00Z",
                        "task_id": "blind-fixture",
                        "seed": "fixed",
                        "mapping": {"A": "baseline", "B": "candidate"},
                        "baseline_run_id": "baseline-run",
                        "candidate_run_id": "candidate-run",
                    }
                ),
                encoding="utf-8",
            )
            judgment_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.blind-semantic-judgment/v0.1-draft",
                        "packet_id": "blind-abc",
                        "task_id": "blind-fixture",
                        "winner": "B",
                        "scores": {
                            "A": {"score": 3.5, "rationale": "adequate"},
                            "B": {"score": 4.4, "rationale": "better"},
                        },
                        "confidence": "medium",
                        "judge_notes": "B is stronger.",
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge-result",
                    "--packet",
                    str(packet_path),
                    "--key",
                    str(key_path),
                    "--judgment",
                    str(judgment_path),
                    "--min-delta",
                    "0.5",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommendation"], "promote_candidate")
        self.assertEqual(payload["winner_side"], "candidate")
        self.assertAlmostEqual(payload["score_delta"], 0.9)


if __name__ == "__main__":
    unittest.main()
