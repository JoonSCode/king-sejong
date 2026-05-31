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
GATE = SEJONG_ROOT / "scripts" / "long_session_experiment_gate.py"
FIXTURE_ROOT = SEJONG_ROOT / "examples" / "outcome-evaluation" / "sejong-long-session"


def run_gate(candidate_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GATE),
            "judge",
            "--task",
            str(FIXTURE_ROOT / "task.json"),
            "--baseline",
            str(FIXTURE_ROOT / "baseline-short.result.json"),
            "--candidate",
            str(FIXTURE_ROOT / candidate_name),
            "--min-delta",
            "0.2",
            "--max-token-ratio",
            "2.0",
        ],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class LongSessionExperimentGateTests(unittest.TestCase):
    def test_require_promotion_requires_filesystem_roots_and_event_logs(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(GATE),
                "judge",
                "--task",
                str(FIXTURE_ROOT / "task.json"),
                "--baseline",
                str(FIXTURE_ROOT / "baseline-short.result.json"),
                "--candidate",
                str(FIXTURE_ROOT / "candidate-long-session.result.json"),
                "--min-delta",
                "0.2",
                "--max-token-ratio",
                "2.0",
                "--require-promotion",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("promotion proof requires --baseline-root", result.stderr)
        self.assertIn("promotion proof requires --baseline-events", result.stderr)

    def test_require_promotion_passes_with_filesystem_roots_and_event_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_root = tmp_path / "baseline-root"
            candidate_root = tmp_path / "candidate-root"
            baseline_root.mkdir()
            candidate_root.mkdir()
            for path in [
                ".agents/skills/sejong/SKILL.md",
                "docs/sejong/scripts/long_session_experiment_gate.py",
                "docs/sejong/scripts/test_long_session_experiment_gate.py",
            ]:
                artifact_path = candidate_root / path
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                artifact_path.write_text(f"{path}\n", encoding="utf-8")
            baseline_events = tmp_path / "baseline.events.jsonl"
            candidate_events = tmp_path / "candidate.events.jsonl"
            baseline_events.write_text(
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 700, "output_tokens": 300}})
                + "\n",
                encoding="utf-8",
            )
            candidate_events.write_text(
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1100, "output_tokens": 500}})
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(FIXTURE_ROOT / "task.json"),
                    "--baseline",
                    str(FIXTURE_ROOT / "baseline-short.result.json"),
                    "--candidate",
                    str(FIXTURE_ROOT / "candidate-long-session.result.json"),
                    "--baseline-root",
                    str(baseline_root),
                    "--candidate-root",
                    str(candidate_root),
                    "--baseline-events",
                    str(baseline_events),
                    "--candidate-events",
                    str(candidate_events),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                    "--require-promotion",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["recommendation"], "promote_candidate")
        self.assertEqual(payload["artifact_contract"]["candidate"]["source"], "filesystem")
        self.assertEqual(payload["resource_budget"]["candidate"]["total_tokens"], 1600)

    def test_task_class_mismatch_blocks_candidate_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task = json.loads((FIXTURE_ROOT / "task.json").read_text(encoding="utf-8"))
            baseline = json.loads((FIXTURE_ROOT / "baseline-short.result.json").read_text(encoding="utf-8"))
            candidate = json.loads((FIXTURE_ROOT / "candidate-long-session.result.json").read_text(encoding="utf-8"))
            task["task_class"] = "strategy-research-synthesis"
            baseline["task_class"] = "strategy-research-synthesis"
            candidate["task_class"] = "code-review-defect-analysis"
            task_path = tmp_path / "task.json"
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(task_path),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["task_class"]["passed"])
        self.assertEqual(payload["recommendation"], "keep_shadowing")
        self.assertIn("candidate task class does not match task", payload["blockers"])

    def test_code_review_task_class_requires_defect_first_critic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task = json.loads((FIXTURE_ROOT / "task.json").read_text(encoding="utf-8"))
            baseline = json.loads((FIXTURE_ROOT / "baseline-short.result.json").read_text(encoding="utf-8"))
            candidate = json.loads((FIXTURE_ROOT / "candidate-long-session.result.json").read_text(encoding="utf-8"))
            task["task_class"] = "code-review-defect-analysis"
            baseline["task_class"] = "code-review-defect-analysis"
            candidate["task_class"] = "code-review-defect-analysis"
            task_path = tmp_path / "task.json"
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(task_path),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["task_class"]["passed"])
        self.assertEqual(payload["recommendation"], "keep_shadowing")
        self.assertIn("defect-first critic evidence missing for code-review-defect-analysis", payload["blockers"])

    def test_non_sejong_baseline_is_not_valid_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_baseline = json.loads((FIXTURE_ROOT / "baseline-short.result.json").read_text(encoding="utf-8"))
            bad_baseline["run_id"] = "baseline-without-sejong"
            bad_baseline["route_sequence"] = []
            bad_baseline_path = Path(tmp) / "baseline-without-sejong.result.json"
            bad_baseline_path.write_text(json.dumps(bad_baseline), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(FIXTURE_ROOT / "task.json"),
                    "--baseline",
                    str(bad_baseline_path),
                    "--candidate",
                    str(FIXTURE_ROOT / "candidate-long-session.result.json"),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["baseline_behavior"]["passed"])
        self.assertEqual(payload["recommendation"], "keep_shadowing")
        self.assertIn("baseline is not current Sejong behavior", payload["blockers"])

    def test_route_only_candidate_does_not_promote_without_better_result_quality(self) -> None:
        result = run_gate("candidate-route-only.result.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.long-session-experiment-gate/v0.1-draft")
        self.assertTrue(payload["baseline_behavior"]["passed"])
        self.assertTrue(payload["intended_behavior"]["passed"])
        self.assertFalse(payload["artifact_contract"]["candidate"]["passed"])
        self.assertLess(payload["outcome_quality"]["score_delta"], 0.2)
        self.assertEqual(payload["recommendation"], "keep_shadowing")
        self.assertIn("candidate artifact contract is incomplete", payload["blockers"])
        self.assertIn("outcome quality delta is below promotion threshold", payload["blockers"])

    def test_long_session_candidate_promotes_only_when_behavior_quality_and_cost_pass(self) -> None:
        result = run_gate("candidate-long-session.result.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.long-session-experiment-gate/v0.1-draft")
        self.assertTrue(payload["baseline_behavior"]["passed"])
        self.assertTrue(payload["intended_behavior"]["passed"])
        self.assertTrue(payload["artifact_contract"]["candidate"]["passed"])
        self.assertGreaterEqual(payload["outcome_quality"]["score_delta"], 0.2)
        self.assertTrue(payload["resource_budget"]["passed"])
        self.assertEqual(payload["recommendation"], "promote_candidate")
        self.assertEqual(payload["blockers"], [])

    def test_route_aliases_count_as_court_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate = json.loads((FIXTURE_ROOT / "candidate-long-session.result.json").read_text(encoding="utf-8"))
            candidate["run_id"] = "candidate-long-session-route-aliases"
            candidate["route_sequence"] = [
                "sejong:long-session-entry",
                "jangyeongsil-research",
                "jiphyeonjeon-decision",
                "uigwe-handoff",
                "seungjeongwon-execution",
                "sillok-verification",
            ]
            candidate_path = Path(tmp) / "candidate-long-session-route-aliases.result.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(FIXTURE_ROOT / "task.json"),
                    "--baseline",
                    str(FIXTURE_ROOT / "baseline-short.result.json"),
                    "--candidate",
                    str(candidate_path),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["intended_behavior"]["passed"])
        self.assertEqual(payload["recommendation"], "promote_candidate")

    def test_allowed_terminal_states_count_as_verified_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            task = json.loads((FIXTURE_ROOT / "task.json").read_text(encoding="utf-8"))
            task["long_session_requirements"]["allowed_terminal_states"] = [
                "verified_complete",
                "completed",
            ]
            task_path = tmp_path / "task.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")

            candidate = json.loads((FIXTURE_ROOT / "candidate-long-session.result.json").read_text(encoding="utf-8"))
            candidate["run_id"] = "candidate-long-session-completed-terminal"
            candidate["terminal_state"] = "completed"
            candidate_path = tmp_path / "candidate-long-session-completed-terminal.result.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(task_path),
                    "--baseline",
                    str(FIXTURE_ROOT / "baseline-short.result.json"),
                    "--candidate",
                    str(candidate_path),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["intended_behavior"]["passed"])
        self.assertEqual(
            payload["intended_behavior"]["allowed_terminal_states"],
            ["verified_complete", "completed"],
        )
        self.assertEqual(payload["recommendation"], "promote_candidate")

    def test_filesystem_artifact_contract_overrides_self_reported_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_root = tmp_path / "baseline"
            candidate_root = tmp_path / "candidate"
            baseline_root.mkdir()
            candidate_root.mkdir()
            (baseline_root / "report.md").write_text("Top 5 Next Actions\nMissing Inputs\n", encoding="utf-8")
            (candidate_root / "report.md").write_text(
                "Comparison Anchors\nTop 5 Next Actions\nMissing Inputs\n",
                encoding="utf-8",
            )
            task = json.loads((FIXTURE_ROOT / "task.json").read_text(encoding="utf-8"))
            task["artifact_contract"] = {
                "required_paths": ["report.md"],
                "forbidden_paths": [],
                "required_checks": ["expected_paths", "repo_conventions", "artifact_shape"],
                "required_markers": [
                    {
                        "path": "report.md",
                        "markers": ["Comparison Anchors", "Top 5 Next Actions", "Missing Inputs"],
                    }
                ],
            }
            task_path = tmp_path / "task.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")
            baseline = json.loads((FIXTURE_ROOT / "baseline-short.result.json").read_text(encoding="utf-8"))
            candidate = json.loads((FIXTURE_ROOT / "candidate-long-session.result.json").read_text(encoding="utf-8"))
            baseline["dimensions"]["artifact_contract"] = {
                "expected_paths": "self-reported",
                "repo_conventions": "self-reported",
                "artifact_shape": "self-reported",
            }
            baseline["artifact_evidence"] = {
                "created_paths": ["report.md"],
                "verified_paths": ["report.md"],
                "checks": {
                    "expected_paths": True,
                    "repo_conventions": True,
                    "artifact_shape": True,
                },
            }
            baseline_path = tmp_path / "baseline.json"
            candidate_path = tmp_path / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(task_path),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--baseline-root",
                    str(baseline_root),
                    "--candidate-root",
                    str(candidate_root),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        artifact_scores = payload["outcome_quality"]["dimension_scores"]["artifact_contract"]
        self.assertEqual(artifact_scores["baseline"]["score"], 0.0)
        self.assertEqual(artifact_scores["candidate"]["score"], 1.0)
        self.assertIn("missing required marker", payload["artifact_contract"]["baseline"]["missing"][0])

    def test_event_jsonl_usage_overrides_self_reported_resource_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_events = tmp_path / "baseline.events.jsonl"
            candidate_events = tmp_path / "candidate.events.jsonl"
            baseline_events.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50}}),
                        json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            candidate_events.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 350, "output_tokens": 250}}),
                        json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}),
                        json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "judge",
                    "--task",
                    str(FIXTURE_ROOT / "task.json"),
                    "--baseline",
                    str(FIXTURE_ROOT / "baseline-short.result.json"),
                    "--candidate",
                    str(FIXTURE_ROOT / "candidate-long-session.result.json"),
                    "--baseline-events",
                    str(baseline_events),
                    "--candidate-events",
                    str(candidate_events),
                    "--min-delta",
                    "0.2",
                    "--max-token-ratio",
                    "2.0",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["resource_budget"]["baseline"]["total_tokens"], 150)
        self.assertEqual(payload["resource_budget"]["candidate"]["total_tokens"], 600)
        self.assertEqual(payload["resource_budget"]["token_ratio"], 4.0)
        self.assertIn("token ratio exceeds budget", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
