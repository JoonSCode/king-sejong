#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
TEAM_EXECUTOR = SEJONG_ROOT / "scripts" / "team_executor.py"
CONTEXT_PATH = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    passed: bool
    detail: str


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_context_fixture() -> dict[str, Any]:
    return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))


def run_hook(
    event_name: str,
    payload: dict[str, Any],
    *,
    context_path: Path | None = None,
    sejong_home: Path | None = None,
    env_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    if sejong_home is not None:
        env["SEJONG_HOME"] = str(sejong_home)
    if env_extra is not None:
        env.update(env_extra)
    command = [sys.executable, str(HOOK_SCRIPT), event_name]
    if context_path is not None:
        command.extend(["--context", str(context_path)])
    result = subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    if result.returncode != 0:
        return {"_error": result.stderr or result.stdout}
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def run_team_command(args: list[str], *, sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEAM_EXECUTOR), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


def scenario_bare_receipt_rejected() -> ScenarioResult:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        context = load_context_fixture()
        context["current_surface"] = "seungjeongwon"
        context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon"]
        context["pending_gates"] = ["seungjeongwon_receipt_required"]
        context["artifact_refs"] = ["native_goal_unavailable"]
        context_path = tmp_path / "context.json"
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
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    return ScenarioResult(
        "bare-native-goal-receipt-rejected",
        decision == "deny",
        f"permissionDecision={decision}",
    )


def scenario_missing_env_context_does_not_fallback() -> ScenarioResult:
    with tempfile.TemporaryDirectory() as tmp:
        sejong_home = Path(tmp)
        matching_context = load_context_fixture()
        matching_context["active_context_id"] = "ctx-adversarial-matching"
        matching_context["repo_root"] = str(REPO_ROOT)
        matching_context["pending_gates"] = ["seungjeongwon_receipt_required"]
        matching_path = sejong_home / "runs" / "matching-repo" / "run" / "king-sejong-context.json"
        matching_path.parent.mkdir(parents=True)
        matching_path.write_text(json.dumps(matching_context), encoding="utf-8")
        missing_context_path = sejong_home / "state" / "missing-active-context.json"
        output = run_hook(
            "UserPromptSubmit",
            {"prompt": "continue", "hook_event_name": "UserPromptSubmit", "cwd": str(REPO_ROOT)},
            sejong_home=sejong_home,
            env_extra={"SEJONG_ACTIVE_CONTEXT": str(missing_context_path)},
        )
    additional = output.get("hookSpecificOutput", {}).get("additionalContext", "")
    passed = "missing_explicit_active_context=true" in additional and "ctx-adversarial-matching" not in additional
    return ScenarioResult("missing-env-context-no-fallback", passed, additional)


def scenario_interpreter_write_bypass_rejected() -> ScenarioResult:
    command = (
        "python3 -c \"from pathlib import Path; "
        "p='docs/sejong/HOOKS.md'; Path(p).write_text('x')\""
    )
    output = run_hook(
        "PreToolUse",
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
        context_path=CONTEXT_PATH,
    )
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    return ScenarioResult(
        "interpreter-write-bypass-rejected",
        decision == "deny",
        f"permissionDecision={decision}",
    )


def scenario_team_duplicate_message_rejected() -> ScenarioResult:
    with tempfile.TemporaryDirectory() as tmp:
        sejong_home = Path(tmp)
        init = run_team_command(
            [
                "init",
                "--run-id",
                "adversarial-duplicate-message",
                "--current-surface",
                "jiphyeonjeon",
                "--worker",
                "critic:critic:bounded risk review",
            ],
            sejong_home=sejong_home,
        )
        if init.returncode != 0:
            return ScenarioResult("team-duplicate-message-rejected", False, init.stderr)
        run_dir = sejong_home / "state" / "team" / "adversarial-duplicate-message"
        opened = run_team_command(["open-round", str(run_dir), "--purpose", "duplicate guard"], sejong_home=sejong_home)
        if opened.returncode != 0:
            return ScenarioResult("team-duplicate-message-rejected", False, opened.stderr)
        base_command = [
            "send-message",
            str(run_dir),
            "--message-id",
            "m-duplicate",
            "--worker-id",
            "critic",
            "--kind",
            "claim",
            "--summary",
            "Duplicate guard.",
        ]
        first = run_team_command(base_command, sejong_home=sejong_home)
        second = run_team_command(base_command, sejong_home=sejong_home)
    passed = first.returncode == 0 and second.returncode != 0 and "duplicate message_id" in second.stderr
    return ScenarioResult(
        "team-duplicate-message-rejected",
        passed,
        f"first={first.returncode} second={second.returncode} stderr={second.stderr.strip()}",
    )


def run_scenarios() -> list[ScenarioResult]:
    return [
        scenario_bare_receipt_rejected(),
        scenario_missing_env_context_does_not_fallback(),
        scenario_interpreter_write_bypass_rejected(),
        scenario_team_duplicate_message_rejected(),
    ]


def main() -> int:
    results = run_scenarios()
    payload = {
        "format": "sejong.adversarial-confidence-pack/v0.1-draft",
        "generated_at": now_utc(),
        "repo_root": str(REPO_ROOT),
        "passed": all(result.passed for result in results),
        "scenarios": [
            {
                "scenario_id": result.scenario_id,
                "passed": result.passed,
                "detail": result.detail,
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
