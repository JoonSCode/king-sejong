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
