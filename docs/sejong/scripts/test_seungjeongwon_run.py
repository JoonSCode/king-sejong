#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from delegation_run_model import JsonObject


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
        "terminal_receipt_ids": ["receipt-worker-a"],
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
