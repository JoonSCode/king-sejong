#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]


@dataclass(frozen=True)
class EvalStep:
    step_id: str
    description: str
    command: tuple[str, ...]
    temp_sejong_home: bool = False


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def python_script(name: str, *args: str) -> tuple[str, ...]:
    return (sys.executable, str(SEJONG_ROOT / "scripts" / name), *args)


def build_steps(*, write_scorecards: bool, include_install_verify: bool) -> list[EvalStep]:
    sejong_surface_args = ["--require-targets"]
    instruction_surface_args = ["--require-targets"]
    if write_scorecards:
        sejong_surface_args.insert(0, "--write")
        instruction_surface_args.insert(0, "--write")

    steps = [
        EvalStep(
            "hook-tests",
            "Hook guardrails, protected-path routes, worker authority, and completion gates",
            python_script("test_king_sejong_hooks.py"),
        ),
        EvalStep(
            "context-tests",
            "Active context start, update, doctor, close, and repo matching",
            python_script("test_sejong_context.py"),
        ),
        EvalStep(
            "seungjeongwon-run-tests",
            "Seungjeongwon run lifecycle and numeric completion guardrails",
            python_script("test_seungjeongwon_run.py"),
        ),
        EvalStep(
            "sillok-trace-tests",
            "Sillok trace security flags and evidence boundaries",
            python_script("test_sillok_trace.py"),
        ),
        EvalStep(
            "cleanup-tests",
            "External Sejong run finalization, pruning, and active-run protection",
            python_script("test_sejong_cleanup.py"),
            temp_sejong_home=True,
        ),
        EvalStep(
            "e2e-tests",
            "External runtime artifact E2E guardrail check",
            python_script("test_king_sejong_e2e.py"),
            temp_sejong_home=True,
        ),
        EvalStep(
            "sejong-surface-benchmark",
            "Seed Sejong routing, guardrail, continuity, and team surface benchmark",
            python_script("benchmark_sejong_surface.py", *sejong_surface_args),
        ),
        EvalStep(
            "instruction-surface-benchmark",
            "Uigwe and Sejong instruction-surface benchmark",
            python_script("benchmark_instruction_surface.py", *instruction_surface_args),
        ),
        EvalStep(
            "json-contracts",
            "JSON schema and example contract validation",
            python_script("validate_json_contracts.py"),
        ),
        EvalStep(
            "sandbox-claim-guard",
            "TeamExecutor worktree isolation wording stays below sandbox claims",
            python_script("team_executor.py", "check-sandbox-claims", "docs/sejong/TEAM_EXECUTOR.md", "docs/sejong/SECURITY.md"),
        ),
    ]
    if include_install_verify:
        steps.append(
            EvalStep(
                "repo-install-verify",
                "Repo-scope managed install verification",
                ("bash", "scripts/install-sejong.sh", "--verify", "."),
            )
        )
    return steps


def run_step(step: EvalStep) -> dict[str, Any]:
    env = os.environ.copy()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if step.temp_sejong_home:
        temp_dir = tempfile.TemporaryDirectory()
        env["SEJONG_HOME"] = temp_dir.name
    start = time.monotonic()
    try:
        result = subprocess.run(
            list(step.command),
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
    elapsed = time.monotonic() - start
    return {
        "id": step.step_id,
        "description": step.description,
        "command": list(step.command),
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "duration_seconds": round(elapsed, 3),
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }


def tail(text: str, *, max_lines: int = 20) -> list[str]:
    lines = text.splitlines()
    return lines[-max_lines:]


def print_step_result(result: dict[str, Any]) -> None:
    status = "ok" if result["passed"] else "fail"
    command = " ".join(result["command"])
    print(f"[{status}] {result['id']} ({result['duration_seconds']}s)")
    print(f"  {command}")
    if not result["passed"]:
        for line in result["stderr_tail"] or result["stdout_tail"]:
            print(f"  | {line}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the King Sejong local deterministic eval pack.")
    parser.add_argument(
        "--write-scorecards",
        action="store_true",
        help="Allow benchmark runners to refresh checked-in scorecard files.",
    )
    parser.add_argument(
        "--install-verify",
        action="store_true",
        help="Also run repo-scope install verification after local evals.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after a failed step and report all failures.",
    )
    parser.add_argument("--json-out", help="Write a machine-readable eval summary to this path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = build_steps(write_scorecards=args.write_scorecards, include_install_verify=args.install_verify)
    summary: dict[str, Any] = {
        "format": "sejong.local-eval-run/v0.1-draft",
        "generated_at": now_utc(),
        "repo_root": str(REPO_ROOT),
        "write_scorecards": args.write_scorecards,
        "install_verify": args.install_verify,
        "steps": [],
    }

    for step in steps:
        result = run_step(step)
        summary["steps"].append(result)
        print_step_result(result)
        if not result["passed"] and not args.keep_going:
            break

    passed = all(step["passed"] for step in summary["steps"]) and len(summary["steps"]) == len(steps)
    summary["passed"] = passed
    summary["completed_steps"] = len(summary["steps"])
    summary["expected_steps"] = len(steps)

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"summary written: {path}")

    if passed:
        print(f"local eval pack ok: {len(steps)}/{len(steps)}")
        return 0
    print(f"local eval pack failed: {summary['completed_steps']}/{len(steps)} steps completed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
