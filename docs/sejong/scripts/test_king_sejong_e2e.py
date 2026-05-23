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


def run_hook(event_name: str, payload: dict, context_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name, "--context", str(context_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout or "{}")


def git_status() -> str:
    return subprocess.check_output(["git", "status", "--short"], cwd=str(REPO_ROOT), text=True)


class KingSejongE2ETests(unittest.TestCase):
    def test_context_route_and_runtime_artifacts_stay_external(self) -> None:
        before = git_status()
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "context.json"
            runtime_dir = Path(os.environ.get("SEJONG_HOME", tmp)) / "runs" / "king-sejong-test"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            context = {
                "format": "king-sejong.context/v0.1-draft",
                "active_context_id": "ctx-e2e",
                "repo_id": "king-sejong-176324a6",
                "repo_root": str(REPO_ROOT),
                "run_id": "e2e",
                "session_id": "session-e2e",
                "route_id": "route-e2e",
                "current_surface": "seungjeongwon",
                "route_sequence": ["jiphyeonjeon", "uigwe"],
                "required_route_sequence": ["jiphyeonjeon", "uigwe", "seungjeongwon"],
                "last_user_intent": "continue",
                "pending_gates": ["verification"],
                "protected_paths": ["docs/sejong/ROUTER.md"],
                "allowed_direct_change_types": ["typo"],
                "evidence_refs": [],
                "artifact_refs": [str(runtime_dir / "plan.packet.json")],
                "team_run_refs": [],
                "subagent_refs": [],
                "exit_conditions": ["user_explicitly_exits_sejong"],
                "last_updated_at": "2026-05-23T00:00:00Z",
            }
            context_path.write_text(json.dumps(context), encoding="utf-8")

            prompt = run_hook("UserPromptSubmit", {"prompt": "진행"}, context_path)
            self.assertIn("King Sejong active context", prompt["hookSpecificOutput"]["additionalContext"])

            blocked = run_hook(
                "PreToolUse",
                {"tool_name": "apply_patch", "tool_input": {"command": "docs/sejong/ROUTER.md"}},
                context_path,
            )
            self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")

            context["route_sequence"].append("seungjeongwon")
            context["pending_gates"] = []
            context_path.write_text(json.dumps(context), encoding="utf-8")
            allowed = run_hook(
                "PreToolUse",
                {"tool_name": "apply_patch", "tool_input": {"command": "docs/sejong/ROUTER.md"}},
                context_path,
            )
            self.assertNotEqual(allowed.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

            after = git_status()
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
