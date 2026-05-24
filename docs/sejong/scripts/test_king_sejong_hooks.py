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
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
CONTEXT_PATH = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"


def run_hook(event_name: str, payload: dict, context_path: Path = CONTEXT_PATH) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name, "--context", str(context_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    output = result.stdout.strip()
    return json.loads(output) if output else {}


class KingSejongHookTests(unittest.TestCase):
    def test_user_prompt_submit_injects_active_context(self) -> None:
        output = run_hook("UserPromptSubmit", {"prompt": "진행", "hook_event_name": "UserPromptSubmit"})
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("King Sejong active context", context)
        self.assertIn("current_surface=seungjeongwon", context)

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

    def test_stop_continues_when_verification_gate_is_pending(self) -> None:
        output = run_hook(
            "Stop",
            {
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": "Done.",
            },
        )
        self.assertEqual(output["decision"], "block")
        self.assertIn("pending King Sejong gates", output["reason"])

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


if __name__ == "__main__":
    unittest.main()
