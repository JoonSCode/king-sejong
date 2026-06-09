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
RUNNER = SEJONG_ROOT / "scripts" / "seungjeongwon_run.py"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class SeungjeongwonRunTests(unittest.TestCase):
    def test_run_lifecycle_requires_attempts_before_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-tagback",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Improve TagBack growth strategy quality.",
                    "--success-criterion",
                    "Candidate score beats baseline by at least 0.12.",
                    "--verification-method",
                    "Run outcome_quality_evaluator compare.",
                    "--todo",
                    "T1|Score current latest SOT baseline|Baseline score is recorded|outcome evaluator",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            premature = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "not enough",
                    "--guardrail-score",
                    "overall=0.99",
                ]
            )
            self.assertNotEqual(premature.returncode, 0)
            self.assertIn("open todos remain", premature.stderr)

            attempt = run_command(
                [
                    "record-attempt",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--hypothesis",
                    "Structured runtime contracts improve actionability.",
                    "--action",
                    "Compared baseline and candidate artifacts.",
                    "--verification",
                    "score_delta >= 0.12",
                    "--result",
                    "pass",
                    "--finding",
                    "Candidate cleared threshold.",
                    "--next-decision",
                    "complete todo",
                ]
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)

            todo = run_command(
                [
                    "complete-todo",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--guardrail-score",
                    "done_criteria_satisfaction=0.99",
                    "--guardrail-score",
                    "verification_evidence_quality=0.99",
                    "--guardrail-score",
                    "scope_containment=0.98",
                    "--guardrail-score",
                    "overall=0.99",
                ]
            )
            self.assertEqual(todo.returncode, 0, todo.stderr)

            complete = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "score_delta=0.28",
                    "--guardrail-score",
                    "selected_leaf_coverage=1.0",
                    "--guardrail-score",
                    "success_criteria_coverage=1.0",
                    "--guardrail-score",
                    "overall=0.99",
                ]
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)

            check = run_command(["check", "--path", str(run_path)])
            self.assertEqual(check.returncode, 0, check.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "sejong.seungjeongwon-run/v0.1-draft")
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["todos"][0]["status"], "completed")

    def test_check_rejects_completed_run_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "bad-run.json"
            run_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.seungjeongwon-run/v0.1-draft",
                        "run_id": "bad",
                        "repo_root": ".",
                        "goal": "Goal",
                        "status": "completed",
                        "success_criteria": ["Done"],
                        "verification_methods": ["Test"],
                        "guardrail_thresholds": {
                            "leaf_guardrail_minimum": 0.98,
                            "leaf_guardrail_aggregate": 0.98,
                            "run_guardrail_aggregate": 0.98,
                            "selected_leaf_coverage": 1.0,
                            "success_criteria_coverage": 1.0,
                        },
                        "todos": [],
                        "attempt_ledger": [],
                        "verification_evidence": [],
                        "guardrail_scores": {},
                        "blockers": [],
                        "uigwe_reentry_requests": [],
                        "created_at": "2026-05-26T00:00:00Z",
                        "updated_at": "2026-05-26T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            result = run_command(["check", "--path", str(run_path)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completed run requires verification evidence", result.stderr)

    def test_check_rejects_completed_todo_below_guardrail_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "guardrail-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-guardrail",
                    "--goal",
                    "Close a strict guardrail leaf.",
                    "--success-criterion",
                    "Leaf closes only after guardrails pass.",
                    "--verification-method",
                    "Run guardrail check.",
                    "--todo",
                    "T1|Implement strict leaf|Guardrails pass|guardrail check",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            attempt = run_command(
                [
                    "record-attempt",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--hypothesis",
                    "The leaf is ready.",
                    "--action",
                    "Checked evidence.",
                    "--verification",
                    "guardrail score",
                    "--result",
                    "partial",
                    "--finding",
                    "Evidence quality is weak.",
                    "--next-decision",
                    "continue",
                ]
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)
            todo = run_command(
                [
                    "complete-todo",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--guardrail-score",
                    "done_criteria_satisfaction=0.97",
                    "--guardrail-score",
                    "overall=0.97",
                ]
            )
        self.assertNotEqual(todo.returncode, 0)
        self.assertIn("guardrail score below threshold", todo.stderr)

    def test_complete_rejects_run_below_coverage_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "coverage-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-coverage",
                    "--goal",
                    "Close the run only when coverage is complete.",
                    "--success-criterion",
                    "All success criteria are covered.",
                    "--verification-method",
                    "Coverage check.",
                    "--todo",
                    "T1|Verify coverage|Coverage is complete|coverage check",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            attempt = run_command(
                [
                    "record-attempt",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--hypothesis",
                    "Coverage passes.",
                    "--action",
                    "Checked coverage.",
                    "--verification",
                    "coverage score",
                    "--result",
                    "pass",
                    "--finding",
                    "Leaf passes.",
                    "--next-decision",
                    "complete",
                ]
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)
            todo = run_command(
                [
                    "complete-todo",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--guardrail-score",
                    "done_criteria_satisfaction=1.0",
                    "--guardrail-score",
                    "overall=1.0",
                ]
            )
            self.assertEqual(todo.returncode, 0, todo.stderr)
            complete = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "coverage checked",
                    "--guardrail-score",
                    "selected_leaf_coverage=0.99",
                    "--guardrail-score",
                    "success_criteria_coverage=1.0",
                    "--guardrail-score",
                    "overall=1.0",
                ]
            )
        self.assertNotEqual(complete.returncode, 0)
        self.assertIn("selected leaf coverage below threshold", complete.stderr)

    def test_checkpoint_replay_preserves_resume_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "durable-run.json"
            checkpoint_path = Path(tmp) / "durable-checkpoint.json"
            replay_path = Path(tmp) / "durable-replay.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-durable",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Preserve Seungjeongwon execution state across compaction.",
                    "--success-criterion",
                    "Resume has the approved goal and active todo state.",
                    "--verification-method",
                    "Replay checkpoint and compare fields.",
                    "--todo",
                    "T1|Implement checkpoint|Checkpoint writes active state|unit test",
                    "--todo",
                    "T2|Replay checkpoint|Replay restores compact state|unit test",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            attempt = run_command(
                [
                    "record-attempt",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--hypothesis",
                    "A derived checkpoint preserves resume-critical state.",
                    "--action",
                    "Created checkpoint command.",
                    "--verification",
                    "Focused replay test.",
                    "--result",
                    "pass",
                    "--finding",
                    "Attempt ledger survives checkpoint.",
                    "--next-decision",
                    "replay",
                    "--evidence-ref",
                    "test_seungjeongwon_run.py::checkpoint_replay",
                ]
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)

            data = json.loads(run_path.read_text(encoding="utf-8"))
            data["verification_evidence"] = ["targeted replay test prepared"]
            data["blockers"] = ["external review pending"]
            data["updated_at"] = "2026-06-09T00:00:00Z"
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            checkpoint = run_command(
                [
                    "checkpoint",
                    "--path",
                    str(run_path),
                    "--output",
                    str(checkpoint_path),
                    "--context-id",
                    "ctx-durable",
                    "--objective-id",
                    "obj-durable",
                ]
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
            checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_data["approved_goal"], data["goal"])
            self.assertEqual([todo["todo_id"] for todo in checkpoint_data["active_todos"]], ["T1", "T2"])
            self.assertEqual(checkpoint_data["attempt_ledger"], data["attempt_ledger"])
            self.assertEqual(checkpoint_data["verification_evidence"], ["targeted replay test prepared"])
            self.assertEqual(checkpoint_data["blockers"], ["external review pending"])

            fresh = run_command(
                [
                    "stale-check",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--path",
                    str(run_path),
                    "--expect-repo-root",
                    ".",
                    "--expect-context-id",
                    "ctx-durable",
                    "--expect-objective-id",
                    "obj-durable",
                ]
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr)

            replay = run_command(
                [
                    "replay",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--path",
                    str(run_path),
                    "--output",
                    str(replay_path),
                    "--expect-repo-root",
                    ".",
                    "--expect-objective-id",
                    "obj-durable",
                ]
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replay_data = json.loads(replay_path.read_text(encoding="utf-8"))
            self.assertEqual(replay_data["format"], "sejong.seungjeongwon-replay/v0.1-draft")
            self.assertEqual(replay_data["approved_goal"], data["goal"])
            self.assertEqual(replay_data["active_todos"], checkpoint_data["active_todos"])
            self.assertEqual(replay_data["attempt_ledger"], data["attempt_ledger"])
            self.assertEqual(replay_data["verification_evidence"], data["verification_evidence"])
            self.assertEqual(replay_data["blockers"], data["blockers"])
            self.assertFalse(replay_data["stale_context_rejected"])

    def test_replay_rejects_stale_checkpoint_after_run_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "stale-run.json"
            checkpoint_path = Path(tmp) / "stale-checkpoint.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-stale",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Reject stale Seungjeongwon resume context.",
                    "--success-criterion",
                    "Replay fails when the active run no longer matches.",
                    "--verification-method",
                    "Mutate the run after checkpoint creation.",
                    "--todo",
                    "T1|Create checkpoint|Checkpoint exists|unit test",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            checkpoint = run_command(
                [
                    "checkpoint",
                    "--path",
                    str(run_path),
                    "--output",
                    str(checkpoint_path),
                    "--context-id",
                    "ctx-stale",
                    "--objective-id",
                    "obj-stale",
                ]
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)

            data = json.loads(run_path.read_text(encoding="utf-8"))
            data["goal"] = "A different active goal must not reuse the stale checkpoint."
            data["updated_at"] = "2026-06-09T01:00:00Z"
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            replay = run_command(
                [
                    "replay",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--path",
                    str(run_path),
                    "--expect-context-id",
                    "ctx-stale",
                    "--expect-objective-id",
                    "obj-stale",
                ]
            )
            self.assertNotEqual(replay.returncode, 0)
            self.assertIn("stale checkpoint source_run_updated_at mismatch", replay.stderr)
            self.assertIn("stale checkpoint approved_goal mismatch", replay.stderr)

            wrong_objective = run_command(
                [
                    "resume",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--expect-objective-id",
                    "obj-other",
                ]
            )
            self.assertNotEqual(wrong_objective.returncode, 0)
            self.assertIn("stale checkpoint objective_id mismatch", wrong_objective.stderr)


if __name__ == "__main__":
    unittest.main()
