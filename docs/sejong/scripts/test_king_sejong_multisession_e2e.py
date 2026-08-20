#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"


def run_context(args: list[str], sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


def start_context(sejong_home: Path, run_id: str, session_id: str) -> Path:
    result = run_context(
        [
            "start",
            "--repo-root",
            str(REPO_ROOT),
            "--run-id",
            run_id,
            "--session-id",
            session_id,
            "--current-surface",
            "seungjeongwon",
            "--pending-gate",
            "seungjeongwon_receipt_required",
            "--last-user-intent",
            f"intent for {session_id}",
        ],
        sejong_home,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    line = next(item for item in result.stdout.splitlines() if item.startswith("run_context="))
    return Path(line.removeprefix("run_context="))


def run_hook(event_name: str, payload: dict[str, Any], sejong_home: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout or "{}")


def payload(event_name: str, session_id: str, turn_id: str) -> dict[str, Any]:
    return {
        "hook_event_name": event_name,
        "session_id": session_id,
        "turn_id": turn_id,
        "cwd": str(REPO_ROOT),
        "prompt": "continue",
        "trigger": "auto",
    }


def additional(output: dict[str, Any]) -> str:
    return str(output.get("hookSpecificOutput", {}).get("additionalContext", ""))


class KingSejongMultisessionE2ETests(unittest.TestCase):
    def test_same_repo_sessions_remain_isolated_across_real_hook_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(sejong_home, "same-repo-a", "session-a")
            start_context(sejong_home, "same-repo-b", "session-b")
            a = run_hook("UserPromptSubmit", payload("UserPromptSubmit", "session-a", "turn-a"), sejong_home)
            b = run_hook("UserPromptSubmit", payload("UserPromptSubmit", "session-b", "turn-b"), sejong_home)
        self.assertIn("ctx-same-repo-a", additional(a))
        self.assertNotIn("ctx-same-repo-b", additional(a))
        self.assertIn("ctx-same-repo-b", additional(b))
        self.assertNotIn("ctx-same-repo-a", additional(b))

    def test_unbound_session_ignores_legacy_pointer_and_repo_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(sejong_home, "legacy-candidate", "session-existing")
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_bytes(context_path.read_bytes())
            output = run_hook("SessionStart", payload("SessionStart", "session-new", "turn-new"), sejong_home)
        self.assertEqual(output, {})

    def test_legacy_active_pointer_lock_does_not_block_context_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "active-pointer.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text('{"legacy":true}', encoding="utf-8")
            result = run_context(
                ["start", "--repo-root", str(REPO_ROOT), "--run-id", "new-run", "--session-id", "session-new"],
                sejong_home,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_broken_bound_artifact_refs_fail_closed_before_compaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(sejong_home, "broken-ref", "session-a")
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["artifact_refs"] = ["missing-seungjeongwon-run.json"]
            context_path.write_text(json.dumps(context), encoding="utf-8")
            output = run_hook("PreCompact", payload("PreCompact", "session-a", "turn-compact"), sejong_home)
        self.assertFalse(output["continue"])
        self.assertIn("broken Seungjeongwon run refs", str(output["stopReason"]))

    def test_compact_observation_keeps_binding_epoch_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(sejong_home, "compact-run", "session-a")
            before_path = next((sejong_home / "state" / "session-bindings").glob("*.json"))
            before = json.loads(before_path.read_text(encoding="utf-8"))
            run_hook("SessionStart", payload("SessionStart", "session-a", "turn-compact"), sejong_home)
            after = json.loads(before_path.read_text(encoding="utf-8"))
        self.assertEqual(after["binding_epoch"], before["binding_epoch"])
        self.assertGreater(after["revision"], before["revision"])
        self.assertEqual(after["last_observation"]["turn_id"], "turn-compact")


if __name__ == "__main__":
    unittest.main()
