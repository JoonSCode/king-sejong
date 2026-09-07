#!/usr/bin/env python3
# noqa: SIZE_OK -- hook contract tests stay colocated for Phase 1 review traceability
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TypeAlias


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
CONTEXT_PATH = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def run_hook(
    event_name: str,
    payload: dict,
    context_path: Path = CONTEXT_PATH,
    *,
    sejong_home: Path | None = None,
) -> JsonObject:
    env = os.environ.copy()
    if sejong_home is not None:
        env["SEJONG_HOME"] = str(sejong_home)
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name, "--context", str(context_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def run_hook_without_context(event_name: str, payload: dict, *, sejong_home: Path) -> dict:  # noqa: DICT_OK
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def run_hook_with_env_context(
    event_name: str,
    payload: dict,
    *,
    sejong_home: Path,
    context_path: Path,
) -> JsonObject:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home), "SEJONG_ACTIVE_CONTEXT": str(context_path)},
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def seungjeongwon_run_fixture(*, status: str = "active", todo_status: str = "pending") -> dict:  # noqa: DICT_OK
    return {
        "format": "sejong.seungjeongwon-run/v0.1-draft",
        "run_id": f"{status}-run",
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
            "verification_refs": ["tests passed"] if status == "completed" else [],
        },
        "goal": "Complete implementation.",
        "status": status,
        "success_criteria": ["All todos verified."],
        "verification_methods": ["Run tests."],
        "guardrail_thresholds": {
            "leaf_guardrail_minimum": 0.98,
            "leaf_guardrail_aggregate": 0.98,
            "run_guardrail_aggregate": 0.98,
            "selected_leaf_coverage": 1.0,
            "success_criteria_coverage": 1.0,
        },
        "todos": [
            {
                "todo_id": "T1",
                "description": "Run tests",
                "done_criteria": "Tests pass",
                "verification_method": "python3 -m unittest",
                "guardrail_scores": {},
                "status": todo_status,
                "attempt_ids": [],
            }
        ]
        if status != "completed"
        else [],
        "attempt_ledger": [],
        "verification_evidence": ["tests passed"] if status == "completed" else [],
        "execution_feedback_refs": [],
        "guardrail_scores": {"selected_leaf_coverage": 1.0, "success_criteria_coverage": 1.0, "overall": 1.0}
        if status == "completed"
        else {},
        "blockers": [],
        "uigwe_reentry_requests": [],
        "created_at": "2026-05-26T00:00:00Z",
        "updated_at": "2026-05-26T00:00:00Z",
    }


def native_goal_unavailable_receipt_fixture() -> dict:  # noqa: DICT_OK
    return {
        "format": "sejong.seungjeongwon-receipt/v0.1-draft",
        "receipt_type": "native_goal_unavailable",
        "status": "recorded",
        "created_by": "seungjeongwon",
        "reason": "Host native goal support is unavailable in this runtime.",
        "created_at": "2026-05-26T00:00:00Z",
        "evidence_refs": ["execution board published"],
    }


class KingSejongHookTests(unittest.TestCase):
    def test_user_prompt_submit_injects_active_context(self) -> None:
        output = run_hook("UserPromptSubmit", {"prompt": "진행", "hook_event_name": "UserPromptSubmit"})
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("King Sejong active context", context)
        self.assertIn("current_surface=seungjeongwon", context)

    def test_user_prompt_submit_injects_current_run_hud_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT)
            context["objective_id"] = "couple-investment-review-board"
            context["objective_refs"] = ["artifacts/review-board-wedge.md"]
            context["last_user_intent"] = "Preserve the couple review-board wedge."
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "다음", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(f"repo_root={REPO_ROOT}", additional)
        self.assertIn("objective_id=couple-investment-review-board", additional)
        self.assertIn("objective_refs=artifacts/review-board-wedge.md", additional)
        self.assertIn("last_user_intent=Preserve the couple review-board wedge.", additional)

    def test_user_prompt_submit_surfaces_repo_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("repo_mismatch=true", additional)
        self.assertIn("refresh the active context", additional)

    def test_user_prompt_submit_repo_mismatch_respects_explicit_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {
                    "prompt": "세종 종료",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                context_path=context_path,
            )
        self.assertEqual(output, {})

    def test_unbound_hook_ignores_stale_pointer_and_matching_repo_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            stale_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            stale_context["active_context_id"] = "ctx-stale"
            stale_context["repo_id"] = "stale-repo"
            stale_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            active_context_path.write_text(json.dumps(stale_context), encoding="utf-8")

            matching_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            matching_context["active_context_id"] = "ctx-matching"
            matching_context["repo_id"] = "matching-repo"
            matching_context["repo_root"] = str(REPO_ROOT)
            matching_context["current_surface"] = "uigwe"
            matching_context["pending_gates"] = ["uigwe_promotion_required"]
            matching_context["last_updated_at"] = "2026-06-01T00:00:00Z"
            matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
            matching_path.parent.mkdir(parents=True)
            matching_path.write_text(json.dumps(matching_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_env_explicit_context_repo_mismatch_does_not_fallback_to_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)

            mismatched_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            mismatched_context["active_context_id"] = "ctx-env-explicit-mismatch"
            mismatched_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            mismatched_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            env_context_path = sejong_home / "state" / "explicit-context.json"
            env_context_path.parent.mkdir(parents=True)
            env_context_path.write_text(json.dumps(mismatched_context), encoding="utf-8")

            matching_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            matching_context["active_context_id"] = "ctx-matching-run-should-not-be-used"
            matching_context["repo_root"] = str(REPO_ROOT)
            matching_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
            matching_path.parent.mkdir(parents=True)
            matching_path.write_text(json.dumps(matching_context), encoding="utf-8")

            output = run_hook_with_env_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
                context_path=env_context_path,
            )

        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("repo_mismatch=true", additional)
        self.assertIn("active_context_id=ctx-env-explicit-mismatch", additional)
        self.assertNotIn("active_context_id=ctx-matching-run-should-not-be-used", additional)
        self.assertNotIn("active_pointer_fallback=true", additional)

    def test_unbound_hook_ignores_malformed_pointer_and_matching_repo_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)
            active_context_path.write_text("{not-json", encoding="utf-8")

            matching_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            matching_context["active_context_id"] = "ctx-matching-after-malformed-pointer"
            matching_context["repo_root"] = str(REPO_ROOT)
            matching_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
            matching_path.parent.mkdir(parents=True)
            matching_path.write_text(json.dumps(matching_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )

        self.assertEqual(output, {})

    def test_unbound_hook_does_not_scan_valid_or_invalid_repo_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            stale_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            stale_context["active_context_id"] = "ctx-stale"
            stale_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            active_context_path.write_text(json.dumps(stale_context), encoding="utf-8")

            valid_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            valid_context["active_context_id"] = "ctx-valid"
            valid_context["repo_root"] = str(REPO_ROOT)
            valid_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            valid_path = sejong_home / "runs" / "app" / "old" / "king-sejong-context.json"
            valid_path.parent.mkdir(parents=True)
            valid_path.write_text(json.dumps(valid_context), encoding="utf-8")

            invalid_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            invalid_context["active_context_id"] = "ctx-invalid"
            invalid_context["repo_root"] = str(REPO_ROOT)
            invalid_context["evidence_refs"] = [{"ref": "not-a-string"}]
            invalid_path = sejong_home / "runs" / "app" / "new" / "king-sejong-context.json"
            invalid_path.parent.mkdir(parents=True)
            invalid_path.write_text(json.dumps(invalid_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_unbound_hook_does_not_rank_repo_contexts_by_freshness_or_objective(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            stale_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            stale_context["active_context_id"] = "ctx-stale-pointer"
            stale_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            stale_context["objective_id"] = "phase-1-core"
            stale_context["task_class"] = "install-maintenance"
            stale_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            active_context_path.write_text(json.dumps(stale_context), encoding="utf-8")

            incompatible_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            incompatible_context["active_context_id"] = "ctx-incompatible-newer"
            incompatible_context["repo_root"] = str(REPO_ROOT)
            incompatible_context["objective_id"] = "different-objective"
            incompatible_context["task_class"] = "strategy-research"
            incompatible_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            incompatible_context["last_updated_at"] = "2026-07-01T00:00:00Z"
            incompatible_path = sejong_home / "runs" / "app" / "incompatible" / "king-sejong-context.json"
            incompatible_path.parent.mkdir(parents=True)
            incompatible_path.write_text(json.dumps(incompatible_context), encoding="utf-8")

            compatible_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            compatible_context["active_context_id"] = "ctx-compatible-semantic-newer"
            compatible_context["repo_root"] = str(REPO_ROOT)
            compatible_context["objective_id"] = "phase-1-core"
            compatible_context["task_class"] = "install-maintenance"
            compatible_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            compatible_context["last_updated_at"] = "2026-06-01T00:00:00Z"
            compatible_path = sejong_home / "runs" / "app" / "compatible" / "king-sejong-context.json"
            compatible_path.parent.mkdir(parents=True)
            compatible_path.write_text(json.dumps(compatible_context), encoding="utf-8")

            old_time = 1_700_000_000
            new_time = old_time + 100
            os.utime(compatible_path, (old_time, old_time))
            os.utime(incompatible_path, (new_time, new_time))

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_hook_ignores_completed_stale_active_pointer_without_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            stale_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            stale_context["active_context_id"] = "ctx-completed-stale"
            stale_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            stale_context["current_surface"] = "seungjeongwon"
            stale_context["route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            stale_context["required_route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            stale_context["pending_gates"] = []
            stale_context["artifact_refs"] = []
            active_context_path.write_text(json.dumps(stale_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )

        self.assertEqual(output, {})

    def test_unbound_hook_ignores_stale_pointer_even_with_pending_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            stale_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            stale_context["active_context_id"] = "ctx-pending-stale"
            stale_context["repo_root"] = str(REPO_ROOT / "not-this-repo")
            stale_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            active_context_path.write_text(json.dumps(stale_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )

        self.assertEqual(output, {})

    def test_hook_does_not_restore_old_repo_context_only_because_refs_are_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)

            old_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            old_context["active_context_id"] = "ctx-old-broken-ref"
            old_context["repo_root"] = str(REPO_ROOT)
            old_context["current_surface"] = "seungjeongwon"
            old_context["route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            old_context["required_route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            old_context["pending_gates"] = []
            old_context["artifact_refs"] = ["missing-seungjeongwon-run.json"]
            old_path = sejong_home / "runs" / "matching-repo" / "old-run" / "king-sejong-context.json"
            old_path.parent.mkdir(parents=True)
            old_path.write_text(json.dumps(old_context), encoding="utf-8")

            output = run_hook_without_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
            )

        self.assertEqual(output, {})

    def test_user_prompt_submit_injects_ambiguity_register_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-test", "active_context_id": "ctx-test"},
                        "stage_id": "intent_clarification",
                        "stage_label": "기획 명확화",
                        "readiness_percent": 67,
                        "blocking_count": 1,
                        "ambiguities": [
                            {
                                "id": "amb-1",
                                "question": "What is unclear?",
                                "why_it_matters": "It changes the implementation boundary.",
                                "options": [{"id": "a", "label": "A", "recommended": True}],
                                "free_response_allowed": True,
                                "status": "open",
                                "blocking": True,
                            }
                        ],
                        "next_required_user_action": "Choose A or provide a free response.",
                        "last_updated_at": "2026-05-24T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "진행", "hook_event_name": "UserPromptSubmit"},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ambiguity_register", additional)
        self.assertIn("readiness=67%", additional)
        self.assertIn("open_ambiguities=1", additional)

    def test_user_prompt_submit_injects_pending_question_obligations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-pending", "active_context_id": "ctx-test"},
                        "stage_id": "intent_clarification",
                        "stage_label": "기획 명확화",
                        "readiness_percent": 92,
                        "blocking_count": 1,
                        "ambiguities": [
                            {
                                "id": "amb-1",
                                "question": "What is explicitly out of scope?",
                                "why_it_matters": "It prevents planning from widening silently.",
                                "options": [{"id": "a", "label": "Keep current scope", "recommended": True}],
                                "free_response_allowed": True,
                                "status": "pending",
                                "blocking": True,
                            }
                        ],
                        "next_required_user_action": "Answer the pending intent question.",
                        "last_updated_at": "2026-06-02T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "진행", "hook_event_name": "UserPromptSubmit"},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pending_question_obligations=1", additional)
        self.assertIn("Answer the pending intent question.", additional)

    def test_user_prompt_submit_injects_continuity_capsule_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule_path = Path(tmp) / "continuity-capsule.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.continuity-capsule/v0.1-draft",
                        "capsule_id": "capsule-test",
                        "active_context_id": "ctx-test",
                        "repo_root": str(REPO_ROOT),
                        "run_id": "run-test",
                        "objective": "Keep AI working context compact.",
                        "task_class": "runtime-contract-design",
                        "current_surface": "uigwe",
                        "route_sequence": ["sejong", "uigwe"],
                        "pending_gates": ["seungjeongwon_receipt_required"],
                        "projection_profile": "standard",
                        "source_artifact_refs": ["king-sejong-context.json"],
                        "evidence_refs": ["sillok-record.jsonl"],
                        "selected_decisions": [
                            {
                                "id": "capsule-index",
                                "summary": "Use capsule as compact artifact index.",
                                "why": "It preserves working state without raw replay.",
                                "refs": ["docs/sejong/HOOKS.md"],
                            }
                        ],
                        "rejected_options": [],
                        "active_blockers": ["hook wiring pending"],
                        "verification_state": {
                            "status": "in_progress",
                            "last_verified_claim": "Projection test is pending.",
                            "refs": ["docs/sejong/scripts/test_king_sejong_hooks.py"],
                        },
                        "next_action": "Wire hook projection.",
                        "do_not_do": ["replay raw logs"],
                        "stale_triggers": ["repo mismatch"],
                        "risk_flags": ["stale_summary"],
                        "last_updated_at": "2026-06-02T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT)
            context["projection_profile"] = "standard"
            context["artifact_refs"] = [str(capsule_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "다음", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("continuity_capsule=capsule-test", additional)
        self.assertIn("task_class=runtime-contract-design", additional)
        self.assertIn("next_action=Wire hook projection.", additional)
        self.assertIn("continuity_decision=Use capsule as compact artifact index.", additional)

    def test_pre_tool_use_blocks_protected_edit_without_route_evidence(self) -> None:
        output = run_hook(
            "PreToolUse",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: docs/sejong/ROUTER.md\n@@\n-old\n+new\n*** End Patch\n"
                },
            },
        )
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("Jiphyeonjeon -> Uigwe -> Seungjeongwon", specific["permissionDecisionReason"])

    def test_pre_tool_use_allows_unprotected_read(self) -> None:
        output = run_hook(
            "PreToolUse",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "sed -n '1,20p' README.md"},
            },
        )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_allows_protected_read_without_route_evidence(self) -> None:
        output = run_hook(
            "PreToolUse",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "sed -n '1,20p' docs/sejong/HOOKS.md"},
            },
        )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_allows_protected_python_read_without_route_evidence(self) -> None:
        output = run_hook(
            "PreToolUse",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python3 -c \"print(open('docs/sejong/HOOKS.md').read()[:1])\""
                },
            },
        )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_blocks_interpreter_protected_writes_without_route_evidence(self) -> None:
        commands = {
            "python_open_write": "python3 -c \"open('docs/sejong/HOOKS.md', 'w').write('x')\"",
            "python_pathlib_write_text": (
                "python3 -c \"from pathlib import Path; "
                "Path('docs/sejong/HOOKS.md').write_text('x')\""
            ),
            "python_heredoc_write_text": (
                "python3 - <<'PY'\n"
                "from pathlib import Path\n"
                "Path('docs/sejong/HOOKS.md').write_text('x')\n"
                "PY"
            ),
            "node_write_file_sync": "node -e \"require('fs').writeFileSync('docs/sejong/HOOKS.md', 'x')\"",
            "ruby_file_write": "ruby -e \"File.write('docs/sejong/HOOKS.md', 'x')\"",
            "perl_open_write": "perl -e 'open my $fh, \">\", \"docs/sejong/HOOKS.md\"; print $fh \"x\"'",
            "php_file_put_contents": "php -r \"file_put_contents('docs/sejong/HOOKS.md', 'x');\"",
            "awk_redirect": "awk 'BEGIN { print \"x\" }' > docs/sejong/HOOKS.md",
            "dd_output_file": "dd if=/dev/null of=docs/sejong/HOOKS.md",
            "install_target": "install /tmp/source.md docs/sejong/HOOKS.md",
            "rsync_target": "rsync /tmp/source.md docs/sejong/HOOKS.md",
            "shell_redirect": "printf 'x' > docs/sejong/HOOKS.md",
        }
        for name, command in commands.items():
            with self.subTest(name=name):
                output = run_hook(
                    "PreToolUse",
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Bash",
                        "tool_input": {"command": command},
                    },
                )
                specific = output["hookSpecificOutput"]
                self.assertEqual(specific["permissionDecision"], "deny")
                self.assertIn("protected self-modification", specific["permissionDecisionReason"])

    def test_post_tool_use_allows_protected_read_without_verification_block(self) -> None:
        output = run_hook(
            "PostToolUse",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "sed -n '1,20p' docs/sejong/HOOKS.md"},
            },
        )
        self.assertEqual(output, {})

    def test_post_tool_use_blocks_protected_write_until_verification_recorded(self) -> None:
        output = run_hook(
            "PostToolUse",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: docs/sejong/HOOKS.md\n@@\n-old\n+new\n*** End Patch\n"
                },
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("Record verification evidence", output["reason"])

    def test_pre_tool_use_blocks_write_before_research_to_uigwe_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "jiphyeonjeon"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon"]
            context["pending_gates"] = ["uigwe_promotion_required"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("research-to-Uigwe gate is pending", specific["permissionDecisionReason"])

    def test_pre_tool_use_allows_write_after_uigwe_promotion_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe"]
            context["required_route_sequence"] = []
            context["pending_gates"] = ["uigwe_promotion_required"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_blocks_write_before_seungjeongwon_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("Seungjeongwon execution receipt is required", specific["permissionDecisionReason"])

    def test_pre_tool_use_allows_write_when_required_route_only_mentions_seungjeongwon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe"]
            context["required_route_sequence"] = ["uigwe", "seungjeongwon"]
            context["pending_gates"] = []
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_allows_write_after_valid_seungjeongwon_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            run_path.write_text(
                json.dumps(seungjeongwon_run_fixture(status="active", todo_status="pending")),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "seungjeongwon"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context["artifact_refs"] = [str(run_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_rejects_bare_native_goal_unavailable_string_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "seungjeongwon"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context["artifact_refs"] = ["native_goal_unavailable"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )

        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("Seungjeongwon execution receipt is required", specific["permissionDecisionReason"])

    def test_pre_tool_use_accepts_typed_native_goal_unavailable_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "native-goal-unavailable-receipt.json"
            receipt_path.write_text(json.dumps(native_goal_unavailable_receipt_fixture()), encoding="utf-8")
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "seungjeongwon"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context["artifact_refs"] = [str(receipt_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )

        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_pre_tool_use_blocks_write_while_uigwe_live_stage_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-intent", "active_context_id": "ctx-test"},
                        "stage_id": "intent_clarification",
                        "stage_label": "기획 명확화",
                        "readiness_percent": 99,
                        "blocking_count": 0,
                        "ambiguities": [],
                        "next_required_user_action": "Raise readiness to 100% or explicitly waive.",
                        "last_updated_at": "2026-06-02T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["sejong", "uigwe"]
            context["required_route_sequence"] = []
            context["pending_gates"] = []
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("Uigwe live-stage obligation", specific["permissionDecisionReason"])

    def test_pre_tool_use_allows_uigwe_register_write_while_live_stage_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-intent", "active_context_id": "ctx-test"},
                        "stage_id": "intent_clarification",
                        "stage_label": "기획 명확화",
                        "readiness_percent": 99,
                        "blocking_count": 0,
                        "ambiguities": [],
                        "next_required_user_action": "Raise readiness to 100% or explicitly waive.",
                        "last_updated_at": "2026-06-02T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["sejong", "uigwe"]
            context["required_route_sequence"] = []
            context["pending_gates"] = []
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "edit",
                    "tool_input": {
                        "command": "python3 docs/sejong/scripts/live_session_orchestrator.py state.json --json --write-register /tmp/amb-live.json"
                    },
                },
                context_path=context_path,
            )
        self.assertNotEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_subagent_stop_rejects_gate_claim(self) -> None:
        output = run_hook(
            "SubagentStop",
            {
                "hook_event_name": "SubagentStop",
                "agent_type": "worker",
                "last_assistant_message": "I approve the Uigwe gate and this is the final decision.",
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("bounded", output["reason"])

    def test_subagent_stop_requires_parseable_bounded_worker_brief(self) -> None:
        output = run_hook(
            "SubagentStop",
            {
                "hook_event_name": "SubagentStop",
                "agent_type": "worker",
                "last_assistant_message": "I found the relevant evidence in the requested files.",
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("bounded worker brief", output["reason"])

    def test_subagent_stop_rejects_invalid_bounded_worker_brief_json(self) -> None:
        output = run_hook(
            "SubagentStop",
            {
                "hook_event_name": "SubagentStop",
                "agent_type": "worker",
                "last_assistant_message": json.dumps(
                    {
                        "format": "sejong.bounded-worker-brief/v0.2-draft",
                        "objective": "Review the route.",
                        "role": "critic",
                    }
                ),
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("Invalid subagent bounded worker brief", output["reason"])

    def test_subagent_stop_accepts_valid_bounded_worker_brief_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["evidence_refs"] = ["brief.md"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "SubagentStop",
                {
                    "hook_event_name": "SubagentStop",
                    "agent_type": "worker",
                    "last_assistant_message": json.dumps(
                        {
                            "format": "sejong.bounded-worker-brief/v0.2-draft",
                            "objective": "Review the route.",
                            "role": "critic",
                            "source_of_truth_refs": ["brief.md"],
                            "allowed_outputs": ["bounded evidence", "risks"],
                            "forbidden_claims": [
                                "Uigwe gate approval",
                                "final synthesis",
                                "final verification",
                                "majority vote",
                                "consensus approval",
                            ],
                            "write_scope": ["none"],
                            "stop_condition": "Return evidence to the Sejong lead.",
                            "evidence_refs": ["brief.md"],
                        }
                    ),
                },
                context_path=context_path,
            )
        self.assertIn("SubagentStop", output["hookSpecificOutput"]["hookEventName"])

    def test_subagent_start_injects_bounded_worker_contract(self) -> None:
        output = run_hook(
            "SubagentStart",
            {
                "hook_event_name": "SubagentStart",
                "agent_type": "critic",
                "worker_role": "critic",
                "worker_scope": "bounded risk review",
            },
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("King Sejong active context", context)
        self.assertIn("Bounded worker contract", context)
        self.assertIn("objective=", context)
        self.assertIn("worker_role=critic", context)
        self.assertIn("worker_scope=bounded risk review", context)
        self.assertIn("source_of_truth_refs=", context)
        self.assertIn("allowed_outputs=", context)
        self.assertIn("forbidden_claims=", context)
        self.assertIn("write_scope=", context)
        self.assertIn("evidence_refs=", context)
        self.assertIn("return_format=", context)
        self.assertIn("stop_condition=", context)

    def test_teammate_idle_rejects_peer_gate_claim(self) -> None:
        output = run_hook(
            "TeammateIdle",
            {
                "hook_event_name": "TeammateIdle",
                "teammate_name": "critic",
                "last_assistant_message": "Consensus approves the gate; this is the final synthesis.",
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("worker authority", output["reason"])

    def test_task_completed_rejects_peer_gate_claim(self) -> None:
        output = run_hook(
            "TaskCompleted",
            {
                "hook_event_name": "TaskCompleted",
                "teammate_name": "critic",
                "last_assistant_message": "The Uigwe gate is approved by majority vote.",
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("worker authority", output["reason"])

    def test_task_completed_rejects_peer_final_verification_claim_variants(self) -> None:
        messages = [
            "Final verification complete; all checks passed.",
            "I completed final verification for the run.",
            "Consensus approval is complete, so the gate is done.",
            "This is the final completion proof.",
        ]
        for message in messages:
            with self.subTest(message=message):
                output = run_hook(
                    "TaskCompleted",
                    {
                        "hook_event_name": "TaskCompleted",
                        "teammate_name": "critic",
                        "last_assistant_message": message,
                    },
                )
                self.assertEqual(output["decision"], "block")
                self.assertIn("worker authority", output["reason"])

    def test_task_created_injects_bounded_worker_contract(self) -> None:
        output = run_hook(
            "TaskCreated",
            {
                "hook_event_name": "TaskCreated",
                "teammate_name": "critic",
                "worker_role": "critic",
                "worker_scope": "bounded risk review",
            },
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Bounded worker contract", context)
        self.assertIn("objective=", context)
        self.assertIn("worker_role=critic", context)
        self.assertIn("worker_scope=bounded risk review", context)
        self.assertIn("write_scope=", context)
        self.assertIn("evidence_refs=", context)
        self.assertIn("forbidden_claims=", context)

    def test_stop_continues_when_verification_gate_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["required_route_sequence"] = []
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("pending King Sejong gates", output["reason"])

    def test_stop_blocks_research_to_uigwe_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "jiphyeonjeon"
            context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon"]
            context["pending_gates"] = ["uigwe_promotion_required"]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Research conclusion: do option A.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("uigwe_promotion_required remains pending", output["reason"])

    def test_stop_allows_route_only_seungjeongwon_history_without_receipt_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "seungjeongwon"
            context["route_sequence"] = ["sejong", "jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["required_route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["pending_gates"] = []
            context["artifact_refs"] = []
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Design comparison complete.",
                },
                context_path=context_path,
            )
        self.assertEqual(output, {})

    def test_stop_blocks_when_seungjeongwon_receipt_gate_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["current_surface"] = "seungjeongwon"
            context["route_sequence"] = ["sejong", "jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["required_route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context["artifact_refs"] = []
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("seungjeongwon_receipt_required", output["reason"])

    def test_optional_questions_do_not_block_approved_work_or_completion(self) -> None:
        for status in ("open", "pending", "answered"):
            for blocking in (False, True):
                with self.subTest(status=status, blocking=blocking), tempfile.TemporaryDirectory() as tmp:
                    register = json.loads(
                        (SEJONG_ROOT / "examples" / "ambiguity-register.example.json").read_text(encoding="utf-8")
                    )
                    register["readiness_percent"] = 100
                    register["blocking_count"] = int(blocking)
                    register["ambiguities"] = [register["ambiguities"][0]]
                    register["ambiguities"][0].update(status=status, blocking=blocking)
                    ambiguity_path = Path(tmp) / "ambiguity-register.json"
                    ambiguity_path.write_text(json.dumps(register), encoding="utf-8")
                    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
                    context.update(
                        current_surface="uigwe",
                        route_sequence=["sejong", "uigwe"],
                        required_route_sequence=[],
                        pending_gates=[],
                        artifact_refs=[str(ambiguity_path)],
                    )
                    context_path = Path(tmp) / "context.json"
                    context_path.write_text(json.dumps(context), encoding="utf-8")
                    write = run_hook(
                        "PreToolUse",
                        {
                            "tool_name": "apply_patch",
                            "tool_input": {"command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"},
                        },
                        context_path=context_path,
                    )
                    stop = run_hook(
                        "Stop",
                        {"stop_hook_active": False, "last_assistant_message": "Verified the approved scope."},
                        context_path=context_path,
                    )
                    self.assertEqual(write.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", blocking)
                    self.assertEqual(stop.get("decision") == "block", blocking)

    def test_stop_continues_when_ambiguity_register_has_open_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-test", "active_context_id": "ctx-test"},
                        "stage_id": "design_clarification",
                        "stage_label": "설계 명확화",
                        "readiness_percent": 99,
                        "blocking_count": 1,
                        "ambiguities": [
                            {
                                "id": "amb-1",
                                "question": "Which design?",
                                "why_it_matters": "The choice changes the contract.",
                                "options": [{"id": "a", "label": "A", "recommended": True}],
                                "free_response_allowed": True,
                                "status": "open",
                                "blocking": True,
                            }
                        ],
                        "next_required_user_action": "Resolve the open design ambiguity.",
                        "last_updated_at": "2026-05-24T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["required_route_sequence"] = []
            context["pending_gates"] = []
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("open King Sejong ambiguity remains", output["reason"])

    def test_stop_blocks_when_question_obligation_is_answered_but_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ambiguity_path = Path(tmp) / "ambiguity-register.json"
            ambiguity_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.ambiguity-register/v0.1-draft",
                        "metadata": {"id": "amb-answered", "active_context_id": "ctx-test"},
                        "stage_id": "design_clarification",
                        "stage_label": "설계 명확화",
                        "readiness_percent": 100,
                        "blocking_count": 1,
                        "ambiguities": [
                            {
                                "id": "amb-1",
                                "question": "Which runtime adapter should own structured choices?",
                                "why_it_matters": "The answer changes the implementation contract.",
                                "options": [{"id": "a", "label": "Codex adapter", "recommended": True}],
                                "free_response_allowed": True,
                                "user_response": "Codex adapter",
                                "status": "answered",
                                "blocking": True,
                            }
                        ],
                        "next_required_user_action": "Resolve or waive the answered design question.",
                        "last_updated_at": "2026-06-02T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["required_route_sequence"] = []
            context["pending_gates"] = []
            context["artifact_refs"] = [str(ambiguity_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("pending King Sejong question obligations remain", output["reason"])

    def test_stop_blocks_active_seungjeongwon_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            run_path.write_text(
                json.dumps(seungjeongwon_run_fixture(status="active", todo_status="in_progress")),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["required_route_sequence"] = []
            context["pending_gates"] = []
            context["artifact_refs"] = [str(run_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "Stop",
                {
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done.",
                },
                context_path=context_path,
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("active Seungjeongwon run remains", output["reason"])

    def test_precompact_blocks_invalid_seungjeongwon_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            invalid_run = seungjeongwon_run_fixture(status="active", todo_status="in_progress")
            invalid_run["run_id"] = "invalid-run"
            invalid_run["guardrail_thresholds"] = {}
            run_path.write_text(
                json.dumps(invalid_run),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(run_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("invalid Seungjeongwon run refs", output["stopReason"])

    def test_precompact_creates_seungjeongwon_checkpoint_for_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_path = tmp_path / "seungjeongwon-run.json"
            run_data = seungjeongwon_run_fixture(status="active", todo_status="in_progress")
            run_data["repo_root"] = str(REPO_ROOT)
            run_path.write_text(json.dumps(run_data), encoding="utf-8")

            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_id"] = "repo-test"
            context["run_id"] = "context-run"
            context["active_context_id"] = "ctx-checkpoint-test"
            context["objective_id"] = "checkpoint-risk-closeout"
            context["repo_root"] = str(REPO_ROOT)
            context["artifact_refs"] = [str(run_path)]
            context_path = tmp_path / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")
            sejong_home = tmp_path / "sejong-home"

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                context_path=context_path,
                sejong_home=sejong_home,
            )

            checkpoint_path = (
                sejong_home
                / "runs"
                / "repo-test"
                / "context-run"
                / "active-run.seungjeongwon-checkpoint.json"
            )
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        self.assertEqual(output, {})
        self.assertEqual(checkpoint["format"], "sejong.seungjeongwon-checkpoint/v0.1-draft")
        self.assertEqual(checkpoint["context_id"], "ctx-checkpoint-test")
        self.assertEqual(checkpoint["objective_id"], "checkpoint-risk-closeout")
        self.assertEqual(checkpoint["source_run_path"], str(run_path.resolve()))
        self.assertEqual(checkpoint["provenance"]["created_by"], "seungjeongwon")
        self.assertIn(str(run_path.resolve()), checkpoint["provenance"]["input_refs"])

    def test_precompact_skips_checkpoint_for_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_path = tmp_path / "seungjeongwon-run.json"
            run_data = seungjeongwon_run_fixture(status="completed")
            run_data["repo_root"] = str(REPO_ROOT)
            run_data["verification_evidence"] = []
            run_path.write_text(json.dumps(run_data), encoding="utf-8")

            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_id"] = "repo-test"
            context["run_id"] = "context-run"
            context["repo_root"] = str(REPO_ROOT)
            context["artifact_refs"] = [str(run_path)]
            context_path = tmp_path / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")
            sejong_home = tmp_path / "sejong-home"

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                context_path=context_path,
                sejong_home=sejong_home,
            )

            checkpoint_path = (
                sejong_home
                / "runs"
                / "repo-test"
                / "context-run"
                / "completed-run.seungjeongwon-checkpoint.json"
            )
            checkpoint_exists = checkpoint_path.exists()
        self.assertEqual(output, {})
        self.assertFalse(checkpoint_exists)

    def test_precompact_allows_missing_implicit_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=Path(tmp),
            )
        self.assertEqual(output, {})

    def test_precompact_blocks_malformed_implicit_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)
            active_context_path.write_text("{not-json", encoding="utf-8")

            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_precompact_blocks_malformed_implicit_active_context_with_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)
            active_context_path.write_text("{not-json", encoding="utf-8")

            matching_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            matching_context["active_context_id"] = "ctx-matching-for-malformed-precompact"
            matching_context["repo_root"] = str(REPO_ROOT)
            matching_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
            matching_path.parent.mkdir(parents=True)
            matching_path.write_text(json.dumps(matching_context), encoding="utf-8")

            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
            )

        self.assertEqual(output, {})

    def test_precompact_blocks_non_object_implicit_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)
            active_context_path.write_text("[]", encoding="utf-8")

            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_precompact_ignores_mismatched_implicit_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context_path = sejong_home / "state" / "active-context.json"
            active_context_path.parent.mkdir(parents=True)

            sibling_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            sibling_context["active_context_id"] = "ctx-sibling"
            sibling_context["repo_root"] = str(REPO_ROOT / "sibling-repo")
            sibling_context["pending_gates"] = ["uigwe_promotion_required"]
            active_context_path.write_text(json.dumps(sibling_context), encoding="utf-8")

            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
            )
        self.assertEqual(output, {})

    def test_unbound_precompact_does_not_scan_matching_repo_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_path = sejong_home / "runs" / "repo-test" / "context-run" / "seungjeongwon-run.json"
            run_path.parent.mkdir(parents=True)
            run_data = seungjeongwon_run_fixture(status="active", todo_status="in_progress")
            run_data["repo_root"] = str(REPO_ROOT)
            run_path.write_text(json.dumps(run_data), encoding="utf-8")

            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_id"] = "repo-test"
            context["run_id"] = "context-run"
            context["active_context_id"] = "ctx-repo-continuation"
            context["repo_root"] = str(REPO_ROOT)
            context["artifact_refs"] = [str(run_path)]
            context_path = run_path.parent / "king-sejong-context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook_without_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
            )
            checkpoint_path = (
                sejong_home
                / "runs"
                / "repo-test"
                / "context-run"
                / "active-run.seungjeongwon-checkpoint.json"
            )
            checkpoint_exists = checkpoint_path.exists()
        self.assertEqual(output, {})
        self.assertFalse(checkpoint_exists)

    def test_user_prompt_submit_missing_env_context_path_does_not_fall_back_to_repo_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            matching_context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            matching_context["active_context_id"] = "ctx-matching"
            matching_context["repo_root"] = str(REPO_ROOT)
            matching_context["pending_gates"] = ["seungjeongwon_receipt_required"]
            matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
            matching_path.parent.mkdir(parents=True)
            matching_path.write_text(json.dumps(matching_context), encoding="utf-8")
            missing_context_path = sejong_home / "state" / "missing-active-context.json"

            output = run_hook_with_env_context(
                "UserPromptSubmit",
                {
                    "prompt": "다음",
                    "hook_event_name": "UserPromptSubmit",
                    "cwd": str(REPO_ROOT),
                },
                sejong_home=sejong_home,
                context_path=missing_context_path,
            )

        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("missing_explicit_active_context=true", additional)
        self.assertIn(str(missing_context_path), additional)
        self.assertNotIn("active_context_id=ctx-matching", additional)

    def test_precompact_blocks_broken_ambiguity_register_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(Path(tmp) / "ambiguity-register.json")]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("broken ambiguity register refs", output["stopReason"])

    def test_precompact_blocks_broken_continuity_capsule_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(Path(tmp) / "continuity-capsule.json")]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("broken continuity capsule refs", output["stopReason"])

    def test_precompact_blocks_invalid_continuity_capsule_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule_path = Path(tmp) / "continuity-capsule.json"
            capsule_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.continuity-capsule/v0.1-draft",
                        "capsule_id": "capsule-invalid",
                    }
                ),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(capsule_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("invalid continuity capsule refs", output["stopReason"])

    def test_precompact_blocks_incomplete_checkpoint(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
            json.dump({"format": "king-sejong.context/v0.1-draft", "active_context_id": "ctx-incomplete"}, handle)
            handle.flush()
            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=Path(handle.name),
            )
        self.assertFalse(output["continue"])
        self.assertIn("missing checkpoint fields", output["stopReason"])

    def test_precompact_blocks_non_object_explicit_context(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
            json.dump(["bad"], handle)
            handle.flush()
            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=Path(handle.name),
            )
        self.assertFalse(output["continue"])
        self.assertIn("context JSON must be an object", output["stopReason"])

    def test_precompact_blocks_missing_explicit_context_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_context_path = Path(tmp) / "missing-context.json"
            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto"},
                context_path=missing_context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("missing explicit active context path", output["stopReason"])
        self.assertIn(str(missing_context_path), output["stopReason"])

    def test_precompact_blocks_missing_env_context_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_path = sejong_home / "runs" / "repo-test" / "context-run" / "seungjeongwon-run.json"
            run_path.parent.mkdir(parents=True)
            run_data = seungjeongwon_run_fixture(status="active", todo_status="in_progress")
            run_data["repo_root"] = str(REPO_ROOT)
            run_path.write_text(json.dumps(run_data), encoding="utf-8")

            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT)
            context["artifact_refs"] = [str(run_path)]
            context_path = run_path.parent / "king-sejong-context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            missing_context_path = Path(tmp) / "missing-env-context.json"
            output = run_hook_with_env_context(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home=sejong_home,
                context_path=missing_context_path,
            )
        self.assertFalse(output["continue"])
        self.assertIn("missing explicit active context path", output["stopReason"])
        self.assertIn(str(missing_context_path), output["stopReason"])

    def test_session_start_compact_injects_active_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            run_path.write_text(
                json.dumps(seungjeongwon_run_fixture(status="active", todo_status="in_progress")),
                encoding="utf-8",
            )
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["artifact_refs"] = [str(run_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            output = run_hook(
                "SessionStart",
                {"hook_event_name": "SessionStart", "source": "compact"},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("active_seungjeongwon_runs=active-run open_todos=1", additional)
        self.assertIn("current_todo=T1", additional)
        self.assertIn("next_action=continue_todo:T1", additional)

    def test_postcompact_is_noop_when_invoked_by_legacy_configuration(self) -> None:
        output = run_hook(
            "PostCompact",
            {"hook_event_name": "PostCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
        )
        self.assertEqual(output, {})

    def test_couple_investment_replay_blocks_write_until_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT)
            context["current_surface"] = "uigwe"
            context["route_sequence"] = ["sejong", "uigwe"]
            context["pending_gates"] = ["seungjeongwon_receipt_required"]
            context["last_user_intent"] = "CoupleInvestmentApp deployment-quality workflow replay."
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            next_prompt = run_hook(
                "UserPromptSubmit",
                {"prompt": "다음", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
                context_path=context_path,
            )
            write_attempt = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "cwd": str(REPO_ROOT),
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                    },
                },
                context_path=context_path,
            )
        self.assertIn("seungjeongwon_receipt_required", next_prompt["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(write_attempt["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
