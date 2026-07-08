#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"
DOCTOR_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_doctor.py"
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"


def run_context(args: list[str], sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


def run_doctor(args: list[str], sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


def run_hook(event_name: str, payload: dict[str, JsonValue], sejong_home: Path) -> dict[str, JsonValue]:
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
    return json.loads(result.stdout or "{}")


def read_json(path: Path) -> dict[str, JsonValue]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fresh_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def context_payload(context_id: str, repo_root: Path, run_id: str) -> dict[str, JsonValue]:
    return {
        "format": "king-sejong.context/v0.1-draft",
        "active_context_id": context_id,
        "repo_id": "king-sejong-e2e",
        "repo_root": str(repo_root),
        "run_id": run_id,
        "session_id": f"session-{run_id}",
        "route_id": f"route-{run_id}",
        "current_surface": "seungjeongwon",
        "route_sequence": ["sejong", "uigwe", "seungjeongwon"],
        "required_route_sequence": ["uigwe", "seungjeongwon"],
        "last_user_intent": "multisession e2e fixture",
        "pending_gates": ["seungjeongwon_receipt_required"],
        "protected_paths": ["docs/sejong/"],
        "allowed_direct_change_types": ["typo"],
        "evidence_refs": [],
        "artifact_refs": [],
        "team_run_refs": [],
        "subagent_refs": [],
        "exit_conditions": ["user_explicitly_exits_sejong"],
        "last_updated_at": fresh_utc_timestamp(),
    }


class KingSejongMultisessionE2ETests(unittest.TestCase):
    def test_active_pointer_fallback_is_reported_for_two_same_repo_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)

            first = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "same-repo-session-a",
                    "--session-id",
                    "session-a",
                    "--current-surface",
                    "uigwe",
                    "--pending-gate",
                    "seungjeongwon_receipt_required",
                    "--last-user-intent",
                    "first same-repo session",
                ],
                sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "same-repo-session-b",
                    "--session-id",
                    "session-b",
                    "--current-surface",
                    "seungjeongwon",
                    "--pending-gate",
                    "seungjeongwon_receipt_required",
                    "--last-user-intent",
                    "second same-repo session",
                ],
                sejong_home,
            )
            self.assertEqual(second.returncode, 0, second.stderr)

            active_path = sejong_home / "state" / "active-context.json"
            stale_pointer = read_json(active_path)
            stale_pointer["repo_root"] = str(REPO_ROOT / "sibling")
            stale_pointer["active_context_id"] = "ctx-stale-pointer"
            write_json(active_path, stale_pointer)

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "continue", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
                sejong_home,
            )

        additional = str(output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("active_context_id=ctx-same-repo-session-b", additional)
        self.assertIn("active_pointer_fallback=true", additional)

    def test_repo_mismatch_warns_without_applying_sibling_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_path = sejong_home / "state" / "active-context.json"
            write_json(active_path, context_payload("ctx-sibling", REPO_ROOT / "sibling", "sibling-run"))

            output = run_hook(
                "UserPromptSubmit",
                {"prompt": "continue", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
                sejong_home,
            )

        additional = str(output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("repo_mismatch=true", additional)
        self.assertIn("active_context_id=ctx-sibling", additional)

    def test_active_pointer_lock_contention_blocks_context_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "active-pointer.lock"
            write_json(
                lock_path,
                {
                    "lock_name": "active-context",
                    "lock_class": "active-pointer",
                    "owner_session_id": "session-owner",
                    "owner_run_id": "run-owner",
                    "owner_device_id": "device-owner",
                    "operation": "publish active context",
                    "created_at": fresh_utc_timestamp(),
                },
            )

            result = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "contending-run",
                    "--session-id",
                    "session-contender",
                    "--last-user-intent",
                    "contending context start",
                ],
                sejong_home,
            )

        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, combined)
        self.assertIn("active-pointer", combined)
        self.assertIn("session-owner", combined)

    def test_broken_artifact_refs_fail_closed_before_compaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_path = sejong_home / "state" / "active-context.json"
            context = context_payload("ctx-broken-ref", REPO_ROOT, "broken-ref-run")
            context["artifact_refs"] = ["missing-seungjeongwon-run.json"]
            write_json(active_path, context)

            output = run_hook(
                "PreCompact",
                {"hook_event_name": "PreCompact", "trigger": "auto", "cwd": str(REPO_ROOT)},
                sejong_home,
            )

        self.assertFalse(output["continue"])
        self.assertIn("broken Seungjeongwon run refs", str(output["stopReason"]))

    def test_cleanup_dry_run_retains_active_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_path = sejong_home / "state" / "active-context.json"
            run_context_path = sejong_home / "runs" / "king-sejong-e2e" / "active-run" / "king-sejong-context.json"
            active_context = context_payload("ctx-active-run", REPO_ROOT, "active-run")
            write_json(active_path, active_context)
            write_json(run_context_path, active_context)
            old_context_path = sejong_home / "runs" / "king-sejong-e2e" / "old-run" / "king-sejong-context.json"
            write_json(old_context_path, context_payload("ctx-old-run", REPO_ROOT, "old-run"))

            result = run_doctor(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "--skip-python-deps",
                    "--json",
                ],
                sejong_home,
            )

            payload = json.loads(result.stdout)
            check_names = {check["name"] for check in payload["checks"]}
            active_run_retained = run_context_path.exists()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(active_run_retained)
        self.assertIn("runtime-cleanup-dry-run", check_names)
        self.assertIn("active-run", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
