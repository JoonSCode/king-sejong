#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
CONTEXT_PATH = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"


def run_hook(event_name: str, payload: dict, context_path: Path = CONTEXT_PATH, *, sejong_home: Path | None = None) -> dict:
    env = os.environ if sejong_home is None else {**os.environ, "SEJONG_HOME": str(sejong_home)}
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


def run_hook_without_context(event_name: str, payload: dict, *, sejong_home: Path) -> dict:
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


def seungjeongwon_run_fixture(*, status: str = "active", todo_status: str = "pending") -> dict:
    return {
        "format": "sejong.seungjeongwon-run/v0.1-draft",
        "run_id": f"{status}-run",
        "repo_root": ".",
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
        "guardrail_scores": {"selected_leaf_coverage": 1.0, "success_criteria_coverage": 1.0, "overall": 1.0}
        if status == "completed"
        else {},
        "blockers": [],
        "uigwe_reentry_requests": [],
        "created_at": "2026-05-26T00:00:00Z",
        "updated_at": "2026-05-26T00:00:00Z",
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

    def test_hook_selects_matching_repo_context_over_stale_active_pointer(self) -> None:
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
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("active_context_id=ctx-matching", additional)
        self.assertNotIn("repo_mismatch=true", additional)

    def test_hook_skips_invalid_matching_repo_context(self) -> None:
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
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("active_context_id=ctx-valid", additional)
        self.assertNotIn("active_context_id=ctx-invalid", additional)

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
            invalid_run = seungjeongwon_run_fixture(status="completed")
            invalid_run["run_id"] = "invalid-run"
            invalid_run["verification_evidence"] = []
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
        self.assertIn("seungjeongwon_checkpoints_created", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(checkpoint["format"], "sejong.seungjeongwon-checkpoint/v0.1-draft")
        self.assertEqual(checkpoint["context_id"], "ctx-checkpoint-test")
        self.assertEqual(checkpoint["objective_id"], "checkpoint-risk-closeout")
        self.assertEqual(checkpoint["source_run_path"], str(run_path.resolve()))

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

    def test_postcompact_injects_active_run_summary(self) -> None:
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
                "PostCompact",
                {"hook_event_name": "PostCompact"},
                context_path=context_path,
            )
        additional = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("active_seungjeongwon_runs=active-run open_todos=1", additional)

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
