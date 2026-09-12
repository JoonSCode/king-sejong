#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delegation_run_model import JsonObject
import seungjeongwon_run as run_module


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


def start_run(path: Path, *todos: str) -> subprocess.CompletedProcess[str]:
    args = [
        "start",
        "--path",
        str(path),
        "--run-id",
        f"run-{path.stem}",
        "--repo-root",
        ".",
        "--goal",
        "Keep execution active until the original goal is verified.",
        "--success-criterion",
        "The goal is verified after all actionable work succeeds.",
        "--verification-method",
        "Run the focused execution-loop checks.",
    ]
    for todo in todos:
        args.extend(("--todo", todo))
    return run_command(args)


def record_attempt(
    path: Path,
    todo_id: str,
    result: str,
    *,
    attempt_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        "record-attempt",
        "--path",
        str(path),
        "--todo-id",
        todo_id,
        "--hypothesis",
        f"Attempt {result} provides current evidence.",
        "--action",
        "Exercise the focused fixture.",
        "--verification",
        "Inspect the explicit result.",
        "--result",
        result,
        "--finding",
        f"The attempt result is {result}.",
        "--next-decision",
        "Complete on pass or try the next hypothesis.",
        "--evidence-ref",
        f"evidence-{todo_id}-{result}",
    ]
    if attempt_id:
        args.extend(("--attempt-id", attempt_id))
    return run_command(args)


def complete_todo(path: Path, todo_id: str) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            "complete-todo",
            "--path",
            str(path),
            "--todo-id",
            todo_id,
            "--guardrail-score",
            "done_criteria_satisfaction=1.0",
            "--guardrail-score",
            "overall=1.0",
        ]
    )


def complete_run(path: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            "complete",
            "--path",
            str(path),
            "--verification-evidence",
            "fresh goal verification passed",
            "--guardrail-score",
            "selected_leaf_coverage=1.0",
            "--guardrail-score",
            "success_criteria_coverage=1.0",
            "--guardrail-score",
            "overall=1.0",
        ]
    )


def consumer_feedback_fixture() -> dict:
    return {
        "format": "uigwe.codex-consumer-feedback/v0.2-draft",
        "visible_todo_events": [
            {
                "event_id": "ev-publish",
                "event_type": "publish",
                "todo_id": "T1",
                "related_todo_ids": [],
                "summary": "Published T1.",
                "status": "pending",
                "evidence_refs": ["plan.packet.json"],
            },
            {
                "event_id": "ev-verify",
                "event_type": "verify",
                "todo_id": "T1",
                "related_todo_ids": [],
                "summary": "Verified T1 evidence.",
                "status": "in_progress",
                "evidence_refs": ["test output"],
            },
        ],
        "escalations": [
            {
                "reason": "No planner re-entry needed.",
                "severity": "low",
                "related_node_ids": ["T1"],
                "recommended_reentry_target": "none",
            }
        ],
    }


def fan_in_receipt_fixture(*, status: str = "passed") -> JsonObject:
    return {
        "format": "sejong.delegation-fan-in-receipt/v0.1-draft",
        "receipt_type": "fan_in",
        "receipt_id": "fan-in-wave-1",
        "run_id": "delegation-run-1",
        "wave_id": "wave-1",
        "required_worker_ids": ["worker-a"],
        "terminal_receipt_ids": ["receipt-worker-a"], "cleanup_receipt_ids": [],
        "aggregate_status": status,
        "blocking_receipt_ids": [] if status == "passed" else ["receipt-worker-a"],
        "authority": "orchestration_evidence_only",
        "created_at": "2026-07-10T00:00:00Z",
    }


def delegation_run_fixture(receipt: JsonObject) -> JsonObject:
    terminal_status = "completed" if receipt["aggregate_status"] == "passed" else receipt["aggregate_status"]
    terminal_receipt: JsonObject = {
        "format": "sejong.delegation-worker-receipt/v0.1-draft",
        "receipt_type": "worker_terminal",
        "receipt_id": "receipt-worker-a",
        "run_id": receipt["run_id"],
        "wave_id": "wave-1",
        "worker_id": "worker-a",
        "backend": "native",
        "backend_worker_ref": "native://worker-a",
        "worker_contract_ref": "contract://worker-a",
        "worker_output_ref": "output://worker-a",
        "terminal_status": terminal_status,
        "summary": "worker-a terminal",
        "evidence_refs": ["evidence://worker-a"],
        "blocker": None if terminal_status == "completed" else "worker-a disposition",
        "authority": "evidence_only",
        "created_at": "2026-07-10T00:00:00Z",
    }
    return {
        "format": "sejong.delegation-run/v0.1-draft",
        "run_id": receipt["run_id"],
        "created_at": "2026-07-10T00:00:00Z",
        "budget": {
            "max_total_workers": 1,
            "max_concurrency": 1,
            "max_spawn_depth": 1,
            "max_rounds": 1,
        },
        "workers": [
            {
                "worker_id": "worker-a",
                "backend": "native",
                "spawn_depth": 0,
                "status": terminal_status,
                "budget_ref": "#/budget",
            }
        ],
        "rounds_started": ["wave:wave-1"],
        "waves": [
            {
                "wave_id": "wave-1",
                "ordinal": 1,
                "depends_on": [],
                "required_worker_ids": ["worker-a"],
                "status": receipt["aggregate_status"],
                "opened_at": "2026-07-10T00:00:00Z",
                "closed_at": "2026-07-10T00:00:00Z",
                "fan_in_receipt_id": receipt["receipt_id"],
            }
        ],
        "receipts": [terminal_receipt, receipt],
    }


class SeungjeongwonRunTests(unittest.TestCase):
    def test_add_fan_in_receipt_preserves_execution_evidence_without_completing_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            receipt_path = Path(tmp) / "fan-in.json"
            delegation_path = Path(tmp) / "delegation-run.json"
            receipt = fan_in_receipt_fixture()
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            delegation_path.write_text(json.dumps(delegation_run_fixture(receipt)), encoding="utf-8")
            start = run_command(
                [
                    "start", "--path", str(run_path), "--run-id", "run-fan-in", "--goal", "Use fan-in evidence.",
                    "--success-criterion", "Fan-in is referenced.", "--verification-method", "Inspect the run.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            added = run_command(
                [
                    "add-fan-in",
                    "--path",
                    str(run_path),
                    "--delegation-run",
                    str(delegation_path),
                    "--receipt",
                    str(receipt_path),
                ]
            )

            self.assertEqual(added.returncode, 0, added.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["delegation_fan_in_refs"], [str(receipt_path.resolve())])
            self.assertEqual(payload["delegation_run_refs"], [str(delegation_path.resolve())])
            self.assertIn(str(delegation_path.resolve()), payload["provenance"]["input_refs"])
            self.assertEqual(payload["status"], "active")
            summary = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(json.loads(summary.stdout)["delegation_fan_in_ref_count"], 1)

    def test_add_fan_in_requires_delegation_run_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            receipt_path = Path(tmp) / "fan-in.json"
            receipt_path.write_text(json.dumps(fan_in_receipt_fixture()), encoding="utf-8")
            self.assertEqual(
                run_command(
                    [
                        "start", "--path", str(run_path), "--run-id", "run-requires-delegation", "--goal", "Require provenance.",
                        "--success-criterion", "Detached receipts are rejected.", "--verification-method", "Inspect state.",
                    ]
                ).returncode,
                0,
            )
            before = run_path.read_bytes()

            added = run_command(["add-fan-in", "--path", str(run_path), "--receipt", str(receipt_path)])

            self.assertNotEqual(added.returncode, 0)
            self.assertIn("--delegation-run", added.stderr)
            self.assertEqual(run_path.read_bytes(), before)

    def test_add_fan_in_rejects_receipt_not_exactly_embedded_in_delegation_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            receipt_path = Path(tmp) / "fabricated-fan-in.json"
            delegation_path = Path(tmp) / "delegation-run.json"
            embedded = fan_in_receipt_fixture()
            fabricated = {**embedded, "terminal_receipt_ids": ["different-receipt"]}
            receipt_path.write_text(json.dumps(fabricated), encoding="utf-8")
            delegation_path.write_text(json.dumps(delegation_run_fixture(embedded)), encoding="utf-8")
            self.assertEqual(
                run_command(
                    [
                        "start", "--path", str(run_path), "--run-id", "run-fabricated-fan-in", "--goal", "Reject fabrication.",
                        "--success-criterion", "Receipt content matches Core.", "--verification-method", "Inspect state.",
                    ]
                ).returncode,
                0,
            )
            before = run_path.read_bytes()

            added = run_command(
                [
                    "add-fan-in",
                    "--path",
                    str(run_path),
                    "--delegation-run",
                    str(delegation_path),
                    "--receipt",
                    str(receipt_path),
                ]
            )

            self.assertNotEqual(added.returncode, 0)
            self.assertIn("does not exactly match", added.stderr)
            self.assertEqual(run_path.read_bytes(), before)

    def test_add_fan_in_rejects_embedded_non_passed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            receipt_path = Path(tmp) / "blocked-fan-in.json"
            delegation_path = Path(tmp) / "delegation-run.json"
            receipt = fan_in_receipt_fixture(status="blocked")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            delegation_path.write_text(json.dumps(delegation_run_fixture(receipt)), encoding="utf-8")
            self.assertEqual(
                run_command(
                    [
                        "start", "--path", str(run_path), "--run-id", "run-blocked-fan-in", "--goal", "Reject blockers.",
                        "--success-criterion", "Only passed fan-in is attached.", "--verification-method", "Inspect state.",
                    ]
                ).returncode,
                0,
            )
            before = run_path.read_bytes()

            added = run_command(
                [
                    "add-fan-in",
                    "--path",
                    str(run_path),
                    "--delegation-run",
                    str(delegation_path),
                    "--receipt",
                    str(receipt_path),
                ]
            )

            self.assertNotEqual(added.returncode, 0)
            self.assertIn("fan-in receipt is not passed", added.stderr)
            self.assertEqual(run_path.read_bytes(), before)

    def test_check_accepts_run_without_optional_delegation_run_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            self.assertEqual(
                run_command(
                    [
                        "start", "--path", str(run_path), "--run-id", "run-legacy-shape", "--goal", "Keep old runs readable.",
                        "--success-criterion", "Optional refs remain optional.", "--verification-method", "Run check.",
                    ]
                ).returncode,
                0,
            )
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload.pop("delegation_run_refs")
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            checked = run_command(["check", "--path", str(run_path)])

            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_check_rejects_broken_fan_in_receipt_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            self.assertEqual(
                run_command(
                    [
                        "start", "--path", str(run_path), "--run-id", "run-broken-fan-in", "--goal", "Reject broken refs.",
                        "--success-criterion", "Refs resolve.", "--verification-method", "Run check.",
                    ]
                ).returncode,
                0,
            )
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["delegation_fan_in_refs"] = [str(Path(tmp) / "missing.json")]
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            checked = run_command(["check", "--path", str(run_path)])

            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("broken delegation fan-in ref", checked.stderr)

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
            self.assertEqual(data["execution_feedback_refs"], [])
            self.assertEqual(data["provenance"]["created_by"], "seungjeongwon")
            self.assertEqual(data["provenance"]["host"], "codex")
            self.assertIn("score_delta=0.28", data["provenance"]["verification_refs"])

    def test_summary_surfaces_current_todo_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "summary-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-summary",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Make continuation state visible.",
                    "--success-criterion",
                    "The next action is clear.",
                    "--verification-method",
                    "Inspect summary.",
                    "--todo",
                    "T1|Implement HUD summary|Summary names the next todo|summary command",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            summary = run_command(["summary", "--path", str(run_path)])
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertIn("run-summary open_todos=1", summary.stdout)
            self.assertIn("current_todo=T1", summary.stdout)
            self.assertIn("next_action=continue_todo:T1", summary.stdout)

            summary_json = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(summary_json.returncode, 0, summary_json.stderr)
            payload = json.loads(summary_json.stdout)
            self.assertEqual(payload["format"], "sejong.seungjeongwon-run-summary/v0.1-draft")
            self.assertEqual(payload["current_todo_id"], "T1")
            self.assertEqual(payload["next_action"], "continue_todo:T1")
            self.assertEqual(payload["execution_feedback_ref_count"], 0)
            self.assertEqual(payload["visible_todo_event_count"], 0)

    def test_check_rejects_broken_execution_feedback_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "broken-feedback-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-broken-feedback",
                    "--goal",
                    "Reject broken execution feedback refs.",
                    "--success-criterion",
                    "Feedback refs resolve.",
                    "--verification-method",
                    "Run check.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            data["execution_feedback_refs"] = [str(Path(tmp) / "missing-feedback.json")]
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = run_command(["check", "--path", str(run_path)])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken execution feedback ref", result.stderr)

    def test_feedback_refs_are_summarized_and_preserved_in_checkpoint_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "feedback-run.json"
            feedback_path = Path(tmp) / "codex-consumer-feedback.json"
            checkpoint_path = Path(tmp) / "feedback-checkpoint.json"
            replay_path = Path(tmp) / "feedback-replay.json"
            feedback_path.write_text(json.dumps(consumer_feedback_fixture()), encoding="utf-8")
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-feedback",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Carry execution feedback through checkpoints.",
                    "--success-criterion",
                    "Feedback refs are preserved.",
                    "--verification-method",
                    "Summary and replay.",
                    "--todo",
                    "T1|Use feedback refs|Feedback survives checkpoint|summary command",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            data["execution_feedback_refs"] = [str(feedback_path)]
            data["updated_at"] = "2026-06-09T00:00:00Z"
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            check = run_command(["check", "--path", str(run_path)])
            self.assertEqual(check.returncode, 0, check.stderr)
            summary = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_payload = json.loads(summary.stdout)
            self.assertEqual(summary_payload["execution_feedback_ref_count"], 1)
            self.assertEqual(summary_payload["latest_execution_feedback_ref"], str(feedback_path))
            self.assertEqual(summary_payload["visible_todo_event_count"], 2)
            self.assertEqual(summary_payload["latest_reentry_target"], "none")

            checkpoint = run_command(
                [
                    "checkpoint",
                    "--path",
                    str(run_path),
                    "--output",
                    str(checkpoint_path),
                    "--context-id",
                    "ctx-feedback",
                    "--objective-id",
                    "obj-feedback",
                ]
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
            checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_data["execution_feedback_refs"], [str(feedback_path)])

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
                    "obj-feedback",
                ]
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replay_data = json.loads(replay_path.read_text(encoding="utf-8"))
            self.assertEqual(replay_data["execution_feedback_refs"], [str(feedback_path)])

    def test_check_rejects_completed_run_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "bad-run.json"
            run_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.seungjeongwon-run/v0.1-draft",
                        "run_id": "bad",
                        "repo_root": ".",
                        "provenance": {
                            "created_by": "seungjeongwon",
                            "source_repo": ".",
                            "source_commit": "unknown",
                            "skill_version": "0.1.0",
                            "host": "codex",
                            "model": "unknown",
                            "generated_at": "2026-05-26T00:00:00Z",
                            "input_refs": [],
                            "verification_refs": [],
                        },
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
                        "execution_feedback_refs": [],
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

    def test_check_rejects_missing_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "missing-provenance-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-missing-provenance",
                    "--goal",
                    "Create a valid run first.",
                    "--success-criterion",
                    "Run exists.",
                    "--verification-method",
                    "Check run.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            del data["provenance"]
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = run_command(["check", "--path", str(run_path)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing provenance", result.stderr)

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
                    "pass",
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

    def test_attempt_result_compatibility_is_explicit(self) -> None:
        for result in ("pass", "passed", "success", "succeeded", "successful", " PASS "):
            with self.subTest(result=result):
                self.assertTrue(run_module.attempt_result_passed(result))
        for result in ("failed", "partial", "ok", ""):
            with self.subTest(result=result):
                self.assertFalse(run_module.attempt_result_passed(result))

    def test_failed_attempt_cannot_complete_todo_or_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "failed-attempt.json"
            self.assertEqual(
                start_run(run_path, "T1|Try implementation|The focused check passes|focused check").returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "failed").returncode, 0)

            todo_result = complete_todo(run_path, "T1")
            run_result = complete_run(run_path)

            self.assertNotEqual(todo_result.returncode, 0)
            self.assertIn("latest attempt result is not passing", todo_result.stderr)
            self.assertNotEqual(run_result.returncode, 0)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["todos"][0]["status"], "in_progress")

    def test_completion_rejects_unresolved_blockers_reentry_and_terminal_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "completion-boundaries.json"
            self.assertEqual(
                start_run(run_path, "T1|Finish work|Work passes|focused check").returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "pass").returncode, 0)
            self.assertEqual(complete_todo(run_path, "T1").returncode, 0)
            self.assertEqual(complete_run(run_path).returncode, 0)
            completed = json.loads(run_path.read_text(encoding="utf-8"))

            mutations = {
                "blockers": lambda data: data.update(blockers=["dependency unresolved"]),
                "reentry": lambda data: data.update(uigwe_reentry_requests=["brainstorming required"]),
                "blocked todo": lambda data: data["todos"][0].update(status="blocked"),
                "invalidated todo": lambda data: data["todos"][0].update(status="invalidated"),
            }
            for label, mutate in mutations.items():
                with self.subTest(label=label):
                    candidate = json.loads(json.dumps(completed))
                    mutate(candidate)
                    run_path.write_text(json.dumps(candidate), encoding="utf-8")
                    checked = run_command(["check", "--path", str(run_path)])
                    self.assertNotEqual(checked.returncode, 0)

    def test_attempt_integrity_rejects_duplicate_and_cross_todo_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "attempt-integrity.json"
            self.assertEqual(
                start_run(
                    run_path,
                    "T1|First task|First task passes|focused check",
                    "T2|Second task|Second task passes|focused check",
                ).returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "pass", attempt_id="A-shared").returncode, 0)
            before = run_path.read_bytes()
            duplicate = record_attempt(run_path, "T2", "pass", attempt_id="A-shared")
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("duplicate attempt_id", duplicate.stderr)
            self.assertEqual(run_path.read_bytes(), before)

            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["todos"][1]["attempt_ids"] = ["A-shared"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            crossed = run_command(["check", "--path", str(run_path)])
            self.assertNotEqual(crossed.returncode, 0)
            self.assertIn("belongs to todo T1", crossed.stderr)

    def test_failed_attempt_reopens_completed_run_and_removes_stale_completion_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "reopen-completed.json"
            self.assertEqual(
                start_run(run_path, "T1|Complete once|Initial check passes|focused check").returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "pass").returncode, 0)
            self.assertEqual(complete_todo(run_path, "T1").returncode, 0)
            self.assertEqual(complete_run(run_path).returncode, 0)

            failed = record_attempt(run_path, "T1", "failed", attempt_id="A-regression")

            self.assertEqual(failed.returncode, 0, failed.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["todos"][0]["status"], "in_progress")
            self.assertEqual(payload["todos"][0]["guardrail_scores"], {})
            self.assertEqual(payload["guardrail_scores"], {})
            self.assertEqual(payload["verification_evidence"], ["fresh goal verification passed"])
            self.assertEqual(payload["provenance"]["verification_refs"], ["fresh goal verification passed"])
            self.assertEqual(payload["attempt_ledger"][-1]["result"], "failed")

    def test_active_run_with_closed_todos_can_wait_for_goal_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "goal-verification.json"
            self.assertEqual(
                start_run(run_path, "T1|Finish leaf|Leaf check passes|focused check").returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "pass").returncode, 0)
            self.assertEqual(complete_todo(run_path, "T1").returncode, 0)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["verification_evidence"] = ["leaf evidence does not yet close the original goal"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            checked = run_command(["check", "--path", str(run_path)])
            summarized = run_command(["summary", "--path", str(run_path), "--json"])

            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(summarized.returncode, 0, summarized.stderr)
            self.assertEqual(json.loads(summarized.stdout)["next_action"], "verify_goal_criteria")

    def test_active_empty_run_with_existing_verification_history_returns_to_goal_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "empty-goal-verification.json"
            self.assertEqual(start_run(run_path).returncode, 0)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["verification_evidence"] = ["prior evidence remains historical"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            summarized = run_command(["summary", "--path", str(run_path), "--json"])

            self.assertEqual(summarized.returncode, 0, summarized.stderr)
            self.assertEqual(json.loads(summarized.stdout)["next_action"], "verify_goal_criteria")

    def test_summary_distinguishes_retry_replanning_reentry_and_independent_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "summary-branches.json"
            self.assertEqual(
                start_run(
                    run_path,
                    "T1|Retry task|Retry succeeds|focused check",
                    "T2|Independent task|Independent task succeeds|focused check",
                ).returncode,
                0,
            )
            self.assertEqual(record_attempt(run_path, "T1", "failed").returncode, 0)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["blockers"] = ["A separate dependency is blocked"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            retry = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertEqual(json.loads(retry.stdout)["next_action"], "retry_todo_with_next_hypothesis:T1")

            payload["todos"][0]["status"] = "invalidated"
            payload["todos"][1]["status"] = "completed"
            payload["todos"][1]["attempt_ids"] = ["A2"]
            payload["todos"][1]["guardrail_scores"] = {"overall": 1.0}
            payload["attempt_ledger"].append(
                {
                    **payload["attempt_ledger"][0],
                    "attempt_id": "A2",
                    "todo_id": "T2",
                    "result": "pass",
                }
            )
            payload["blockers"] = []
            payload["todos"][0]["status"] = "blocked"
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            blocked = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            self.assertEqual(json.loads(blocked.stdout)["next_action"], "resolve_blocker_or_reenter_uigwe")

            payload["todos"][0]["status"] = "invalidated"
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            replanning = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(replanning.returncode, 0, replanning.stderr)
            self.assertEqual(json.loads(replanning.stdout)["next_action"], "replan_invalidated_todo:T1")

            payload["uigwe_reentry_requests"] = ["design no longer satisfies the goal"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            reentry = run_command(["summary", "--path", str(run_path), "--json"])
            self.assertEqual(reentry.returncode, 0, reentry.stderr)
            self.assertEqual(json.loads(reentry.stdout)["next_action"], "reenter_uigwe")

    def test_add_and_replace_todo_preserve_original_scope_until_replacements_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "replace-todo.json"
            self.assertEqual(
                start_run(run_path, "T1|Original task|Original scope is resolved|focused check").returncode,
                0,
            )
            added = run_command(
                [
                    "add-todo",
                    "--path",
                    str(run_path),
                    "--todo",
                    "T2|Independent task|Independent task passes|focused check",
                ]
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            replaced = run_command(
                [
                    "replace-todo",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--replacement-todo",
                    "T1a|First replacement|First replacement passes|focused check",
                    "--replacement-todo",
                    "T1b|Second replacement|Second replacement passes|focused check",
                ]
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["todos"][0]["status"], "replaced")
            self.assertEqual(payload["todos"][0]["replacement_todo_ids"], ["T1a", "T1b"])
            self.assertNotEqual(complete_run(run_path).returncode, 0)

            for todo_id in ("T2", "T1a", "T1b"):
                self.assertEqual(record_attempt(run_path, todo_id, "passed").returncode, 0)
                self.assertEqual(complete_todo(run_path, todo_id).returncode, 0)
            self.assertEqual(complete_run(run_path).returncode, 0)

    def test_replace_todo_rejects_invalid_links_and_preserves_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "invalid-replacement.json"
            self.assertEqual(
                start_run(run_path, "T1|Original task|Original scope is resolved|focused check").returncode,
                0,
            )
            invalid_commands = (
                ["replace-todo", "--path", str(run_path), "--todo-id", "missing", "--replacement-todo", "T2|New|Done|Check"],
                ["replace-todo", "--path", str(run_path), "--todo-id", "T1", "--replacement-todo", "T1|Self|Done|Check"],
                ["add-todo", "--path", str(run_path), "--todo", "T1|Duplicate|Done|Check"],
            )
            for command in invalid_commands:
                with self.subTest(command=command[0:4]):
                    before = run_path.read_bytes()
                    result = run_command(command)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(run_path.read_bytes(), before)

            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["todos"].extend(
                [
                    {**run_module.parse_todo("T2|Second|Done|Check"), "status": "replaced", "replacement_todo_ids": ["T1"]},
                ]
            )
            payload["todos"][0]["status"] = "replaced"
            payload["todos"][0]["replacement_todo_ids"] = ["T2"]
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            cycled = run_command(["check", "--path", str(run_path)])
            self.assertNotEqual(cycled.returncode, 0)
            self.assertIn("replacement cycle", cycled.stderr)

            for malformed in ([], 7, {"bad": "shape"}, [7], [{}]):
                with self.subTest(malformed=malformed):
                    candidate = json.loads(json.dumps(payload))
                    candidate["todos"][0]["replacement_todo_ids"] = malformed
                    run_path.write_text(json.dumps(candidate), encoding="utf-8")
                    checked = run_command(["check", "--path", str(run_path)])
                    self.assertNotEqual(checked.returncode, 0)
                    self.assertNotIn("Traceback", checked.stderr)
                    self.assertIn("replacement_todo_ids", checked.stderr)

    def test_atomic_write_failure_preserves_original_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atomic.json"
            path.write_text('{"original": true}\n', encoding="utf-8")
            before = path.read_bytes()

            with patch.object(run_module.os, "replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaises(OSError):
                    run_module.write_json(path, {"replacement": True})

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_checkpoint_replay_preserves_replacement_links_and_detects_stale_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "replacement-checkpoint-run.json"
            checkpoint_path = Path(tmp) / "replacement-checkpoint.json"
            replay_path = Path(tmp) / "replacement-replay.json"
            self.assertEqual(
                start_run(run_path, "T1|Original task|Original scope is resolved|focused check").returncode,
                0,
            )
            self.assertEqual(
                run_command(
                    [
                        "replace-todo",
                        "--path",
                        str(run_path),
                        "--todo-id",
                        "T1",
                        "--replacement-todo",
                        "T1a|Replacement|Replacement passes|focused check",
                    ]
                ).returncode,
                0,
            )
            self.assertEqual(
                run_command(
                    [
                        "checkpoint",
                        "--path",
                        str(run_path),
                        "--output",
                        str(checkpoint_path),
                        "--context-id",
                        "ctx-replacement",
                        "--objective-id",
                        "obj-replacement",
                    ]
                ).returncode,
                0,
            )
            checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            for malformed in (None, "bad", [None], ["bad"]):
                with self.subTest(malformed_checkpoint_statuses=malformed):
                    candidate = json.loads(json.dumps(checkpoint_payload))
                    candidate["todo_statuses"] = malformed
                    failures = run_module.checkpoint_failures(candidate)
                    self.assertTrue(any("todo_statuses" in failure for failure in failures))
            original_status = next(item for item in checkpoint_payload["todo_statuses"] if item["todo_id"] == "T1")
            self.assertEqual(original_status["replacement_todo_ids"], ["T1a"])

            replayed = run_command(
                [
                    "replay",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--path",
                    str(run_path),
                    "--output",
                    str(replay_path),
                    "--expect-context-id",
                    "ctx-replacement",
                    "--expect-objective-id",
                    "obj-replacement",
                ]
            )
            self.assertEqual(replayed.returncode, 0, replayed.stderr)
            replay_payload = json.loads(replay_path.read_text(encoding="utf-8"))
            self.assertEqual(replay_payload["todo_statuses"], checkpoint_payload["todo_statuses"])

            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["todos"][0]["replacement_todo_ids"] = []
            payload["updated_at"] = "2026-09-12T08:00:00Z"
            run_path.write_text(json.dumps(payload), encoding="utf-8")
            stale = run_command(
                [
                    "stale-check",
                    "--checkpoint",
                    str(checkpoint_path),
                    "--path",
                    str(run_path),
                ]
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertTrue(
                "replacement_todo_ids must be a non-empty list" in stale.stderr
                or "stale checkpoint todo_statuses mismatch" in stale.stderr
            )

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
            self.assertEqual(checkpoint_data["provenance"]["created_by"], "seungjeongwon")
            self.assertIn(str(run_path.resolve()), checkpoint_data["provenance"]["input_refs"])
            self.assertIn("targeted replay test prepared", checkpoint_data["provenance"]["verification_refs"])
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
