#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GATE_FORMAT = "sejong.integrated-quality-gate/v0.1-draft"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_payload: dict[str, Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=json.dumps(input_payload) if input_payload is not None else None,
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
    )


def check_result(check_id: str, passed: bool, detail: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "detail": detail,
        "evidence": evidence or [],
    }


def parse_hook_output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if result.returncode != 0:
        return {"error": result.stderr or result.stdout}
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def outcome_quality_check(sejong_root: Path, repo_root: Path, work_dir: Path) -> tuple[dict[str, Any], float]:
    evaluator = sejong_root / "scripts" / "outcome_quality_evaluator.py"
    fixture = sejong_root / "examples" / "outcome-evaluation" / "tagback-growth"
    comparison_path = work_dir / "tagback-comparison.result.json"
    result = run_command(
        [
            sys.executable,
            str(evaluator),
            "compare",
            "--task",
            str(fixture / "task.json"),
            "--baseline",
            str(fixture / "baseline-current-sot.result.json"),
            "--candidate",
            str(fixture / "candidate-runtime-contracts.result.json"),
            "--min-delta",
            "0.12",
            "--write",
            str(comparison_path),
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return check_result("outcome_quality_promotes_candidate", False, result.stderr or result.stdout), 0.0
    payload = json.loads(result.stdout)
    passed = payload.get("recommendation") == "promote_candidate" and payload.get("score_delta", 0) >= 0.12
    detail = (
        f"baseline={payload.get('baseline_score')} candidate={payload.get('candidate_score')} "
        f"delta={payload.get('score_delta')} recommendation={payload.get('recommendation')}"
    )
    return check_result("outcome_quality_promotes_candidate", passed, detail, [str(comparison_path)]), float(
        payload.get("score_delta", 0)
    )


def research_gate_check(sejong_root: Path, repo_root: Path, work_dir: Path) -> dict[str, Any]:
    hook = sejong_root / "scripts" / "king_sejong_hooks.py"
    context = load_json(sejong_root / "examples" / "king-sejong-context.example.json")
    context["current_surface"] = "jiphyeonjeon"
    context["route_sequence"] = ["jangyeongsil", "jiphyeonjeon"]
    context["pending_gates"] = ["uigwe_promotion_required"]
    context["artifact_refs"] = []
    context_path = work_dir / "research-gate-context.json"
    write_json(context_path, context)
    result = run_command(
        [sys.executable, str(hook), "PreToolUse", "--context", str(context_path)],
        cwd=repo_root,
        input_payload={
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"},
        },
    )
    output = parse_hook_output(result)
    specific = output.get("hookSpecificOutput") or {}
    passed = specific.get("permissionDecision") == "deny" and "research-to-Uigwe gate" in specific.get(
        "permissionDecisionReason", ""
    )
    return check_result(
        "research_to_uigwe_gate_blocks_write",
        passed,
        specific.get("permissionDecisionReason") or output.get("error", "missing denial"),
        [str(context_path)],
    )


def seungjeongwon_run_check(sejong_root: Path, repo_root: Path, work_dir: Path) -> dict[str, Any]:
    runner = sejong_root / "scripts" / "seungjeongwon_run.py"
    hook = sejong_root / "scripts" / "king_sejong_hooks.py"
    run_path = work_dir / "seungjeongwon-run.json"
    start = run_command(
        [
            sys.executable,
            str(runner),
            "start",
            "--path",
            str(run_path),
            "--run-id",
            "integrated-tagback-run",
            "--repo-root",
            str(repo_root),
            "--goal",
            "Prove enhanced Sejong improves the TagBack growth outcome artifact.",
            "--success-criterion",
            "Outcome comparison recommends promote_candidate with delta >= 0.12.",
            "--verification-method",
            "Run outcome_quality_evaluator compare.",
            "--todo",
            "TQ|Run paired outcome quality gate|Candidate beats baseline by threshold|outcome_quality_evaluator compare",
        ],
        cwd=repo_root,
    )
    if start.returncode != 0:
        return check_result("seungjeongwon_active_run_blocks_stop_until_verified", False, start.stderr)

    context = load_json(sejong_root / "examples" / "king-sejong-context.example.json")
    context["pending_gates"] = []
    context["route_sequence"] = ["jiphyeonjeon", "uigwe", "seungjeongwon"]
    context["current_surface"] = "seungjeongwon"
    context["artifact_refs"] = [str(run_path)]
    context_path = work_dir / "seungjeongwon-context.json"
    write_json(context_path, context)

    blocked = run_command(
        [sys.executable, str(hook), "Stop", "--context", str(context_path)],
        cwd=repo_root,
        input_payload={"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "Done."},
    )
    blocked_output = parse_hook_output(blocked)
    blocked_ok = blocked_output.get("decision") == "block" and "active Seungjeongwon run remains" in blocked_output.get(
        "reason", ""
    )

    commands = [
        [
            sys.executable,
            str(runner),
            "record-attempt",
            "--path",
            str(run_path),
            "--todo-id",
            "TQ",
            "--hypothesis",
            "Runtime contracts improve result quality when compared against the same rubric.",
            "--action",
            "Ran deterministic TagBack paired outcome comparison.",
            "--verification",
            "score_delta >= 0.12 and recommendation=promote_candidate",
            "--result",
            "pass",
            "--finding",
            "Candidate artifact cleared the quality threshold.",
            "--next-decision",
            "complete todo",
            "--evidence-ref",
            str(work_dir / "tagback-comparison.result.json"),
        ],
        [sys.executable, str(runner), "complete-todo", "--path", str(run_path), "--todo-id", "TQ"],
        [sys.executable, str(runner), "complete", "--path", str(run_path), "--verification-evidence", "score_delta>=0.12"],
        [sys.executable, str(runner), "check", "--path", str(run_path)],
    ]
    command_results = [run_command(command, cwd=repo_root) for command in commands]
    completed_ok = all(result.returncode == 0 for result in command_results)

    final = run_command(
        [sys.executable, str(hook), "Stop", "--context", str(context_path)],
        cwd=repo_root,
        input_payload={"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "Done."},
    )
    final_output = parse_hook_output(final)
    final_ok = final_output == {}

    passed = blocked_ok and completed_ok and final_ok
    detail = (
        "active Stop blocked before verification; completed run validated and Stop returned no block"
        if passed
        else f"blocked_ok={blocked_ok} completed_ok={completed_ok} final_ok={final_ok}"
    )
    return check_result(
        "seungjeongwon_active_run_blocks_stop_until_verified",
        passed,
        detail,
        [str(run_path), str(context_path)],
    )


def team_persuasion_check(sejong_root: Path, repo_root: Path, work_dir: Path) -> dict[str, Any]:
    team = sejong_root / "scripts" / "team_executor.py"
    sejong_home = work_dir / "sejong-home"
    env = {**os.environ, "SEJONG_HOME": str(sejong_home)}
    run_id = "integrated-team"
    run_dir = sejong_home / "state" / "team" / run_id
    commands = [
        [
            sys.executable,
            str(team),
            "init",
            "--run-id",
            run_id,
            "--current-surface",
            "jiphyeonjeon",
            "--worker",
            "critic:critic:challenge growth strategy",
            "--worker",
            "operator:operator:execution feasibility",
        ],
        [
            sys.executable,
            str(team),
            "open-round",
            str(run_dir),
            "--round-id",
            "persuade-1",
            "--purpose",
            "persuade opposing perspectives before lead synthesis",
            "--round-kind",
            "persuasion",
            "--max-duration-minutes",
            "30",
        ],
        [
            sys.executable,
            str(team),
            "send-message",
            str(run_dir),
            "--message-id",
            "m1",
            "--round-id",
            "persuade-1",
            "--worker-id",
            "critic",
            "--kind",
            "question",
            "--recipient",
            "worker:operator",
            "--summary",
            "What metric proves this strategy is not just marketing theater?",
            "--requires-response",
        ],
        [
            sys.executable,
            str(team),
            "send-message",
            str(run_dir),
            "--message-id",
            "m2",
            "--round-id",
            "persuade-1",
            "--worker-id",
            "operator",
            "--kind",
            "response",
            "--target-message-id",
            "m1",
            "--recipient",
            "worker:critic",
            "--summary",
            "First retrieval after tag creation is the proof metric.",
        ],
        [
            sys.executable,
            str(team),
            "close-round",
            str(run_dir),
            "persuade-1",
            "--closed-reason",
            "apparent_convergence",
        ],
        [sys.executable, str(team), "check", str(run_dir)],
    ]
    results = [run_command(command, cwd=repo_root, env=env) for command in commands]
    passed = all(result.returncode == 0 for result in results)
    detail = "persuasion round opened, exchanged target-message mailbox replies, closed, and checked"
    if not passed:
        detail = "\n".join(result.stderr or result.stdout for result in results if result.returncode != 0)
    return check_result(
        "team_persuasion_round_uses_existing_mailbox_contract",
        passed,
        detail,
        [str(run_dir / "rounds.json"), str(run_dir / "mailbox.jsonl")],
    )


def feedback_contract_check(sejong_root: Path) -> dict[str, Any]:
    visible = load_json(sejong_root / "examples" / "codex-consumer-feedback-visible-todo-events.example.json")
    paired = load_json(sejong_root / "examples" / "codex-consumer-feedback-paired-comparison.example.json")
    visible_events = visible.get("visible_todo_events") or []
    paired_comparison = paired.get("paired_result_comparison") or {}
    has_redefine = any(event.get("event_type") == "redefine" for event in visible_events)
    has_replace = any(event.get("event_type") == "replace" for event in visible_events)
    promotes_candidate = paired_comparison.get("final_recommendation") == "promote_candidate"
    has_owner_perspective = any(
        perspective.get("perspective_id") == "vp_actionability"
        for perspective in paired.get("verification_perspectives") or []
    )
    passed = has_redefine and has_replace and promotes_candidate and has_owner_perspective
    return check_result(
        "visible_todo_and_paired_result_feedback_still_present",
        passed,
        (
            "visible todo redefinition/replacement and paired result comparison remain present"
            if passed
            else f"has_redefine={has_redefine} has_replace={has_replace} promotes_candidate={promotes_candidate} has_owner_perspective={has_owner_perspective}"
        ),
        [
            str(sejong_root / "examples" / "codex-consumer-feedback-visible-todo-events.example.json"),
            str(sejong_root / "examples" / "codex-consumer-feedback-paired-comparison.example.json"),
        ],
    )


def product_evidence_check(sejong_root: Path, repo_root: Path) -> dict[str, Any]:
    gate = sejong_root / "scripts" / "product_evidence_gate.py"
    fixture = sejong_root / "examples" / "outcome-evaluation" / "tagback-growth"
    plan = fixture / "field-validation-plan.json"
    result_fixture = fixture / "field-validation-result.example.json"
    plan_result = run_command([sys.executable, str(gate), "check-plan", "--plan", str(plan)], cwd=repo_root)
    judge_result = run_command(
        [
            sys.executable,
            str(gate),
            "judge-result",
            "--plan",
            str(plan),
            "--result",
            str(result_fixture),
            "--require-success",
        ],
        cwd=repo_root,
    )
    if plan_result.returncode != 0 or judge_result.returncode != 0:
        return check_result(
            "product_evidence_gate_requires_external_success_evidence",
            False,
            (plan_result.stderr or plan_result.stdout) + (judge_result.stderr or judge_result.stdout),
            [str(plan), str(result_fixture)],
        )
    plan_payload = json.loads(plan_result.stdout)
    result_payload = json.loads(judge_result.stdout)
    passed = (
        plan_payload.get("status") == "ready_for_field_test"
        and not plan_payload.get("can_claim_product_success")
        and result_payload.get("status") == "success_supported"
        and result_payload.get("can_claim_product_success")
    )
    return check_result(
        "product_evidence_gate_requires_external_success_evidence",
        passed,
        (
            "field-validation plan cannot claim success; external result fixture supports success claim"
            if passed
            else f"plan_status={plan_payload.get('status')} result_status={result_payload.get('status')}"
        ),
        [str(plan), str(result_fixture)],
    )


def long_session_gate_check(sejong_root: Path, repo_root: Path, work_dir: Path) -> dict[str, Any]:
    gate = sejong_root / "scripts" / "long_session_experiment_gate.py"
    fixture = sejong_root / "examples" / "outcome-evaluation" / "sejong-long-session"
    route_only_path = work_dir / "long-session-route-only.result.json"
    promoted_path = work_dir / "long-session-promoted.result.json"
    baseline_root = work_dir / "long-session-baseline-root"
    candidate_root = work_dir / "long-session-candidate-root"
    baseline_events = work_dir / "long-session-baseline.events.jsonl"
    candidate_events = work_dir / "long-session-candidate.events.jsonl"

    baseline_root.mkdir(parents=True, exist_ok=True)
    candidate_root.mkdir(parents=True, exist_ok=True)
    for path in [
        ".agents/skills/sejong/SKILL.md",
        "docs/sejong/scripts/long_session_experiment_gate.py",
        "docs/sejong/scripts/test_long_session_experiment_gate.py",
    ]:
        artifact_path = candidate_root / path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{path}\n", encoding="utf-8")
    baseline_events.write_text(
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 700, "output_tokens": 300}}) + "\n",
        encoding="utf-8",
    )
    candidate_events.write_text(
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1100, "output_tokens": 500}}) + "\n",
        encoding="utf-8",
    )

    common = [
        sys.executable,
        str(gate),
        "judge",
        "--task",
        str(fixture / "task.json"),
        "--baseline",
        str(fixture / "baseline-short.result.json"),
        "--min-delta",
        "0.2",
        "--max-token-ratio",
        "2.0",
    ]
    route_only = run_command(
        [
            *common,
            "--candidate",
            str(fixture / "candidate-route-only.result.json"),
            "--write",
            str(route_only_path),
        ],
        cwd=repo_root,
    )
    promoted = run_command(
        [
            *common,
            "--candidate",
            str(fixture / "candidate-long-session.result.json"),
            "--baseline-root",
            str(baseline_root),
            "--candidate-root",
            str(candidate_root),
            "--baseline-events",
            str(baseline_events),
            "--candidate-events",
            str(candidate_events),
            "--write",
            str(promoted_path),
            "--require-promotion",
        ],
        cwd=repo_root,
    )
    if route_only.returncode != 0 or promoted.returncode != 0:
        return check_result(
            "long_session_gate_requires_strict_task_class_evidence",
            False,
            (route_only.stderr or route_only.stdout) + (promoted.stderr or promoted.stdout),
            [str(route_only_path), str(promoted_path)],
        )

    route_payload = json.loads(route_only.stdout)
    promoted_payload = json.loads(promoted.stdout)
    route_only_rejected = (
        route_payload.get("recommendation") == "keep_shadowing"
        and "outcome quality delta is below promotion threshold" in route_payload.get("blockers", [])
    )
    strict_promoted = (
        promoted_payload.get("recommendation") == "promote_candidate"
        and promoted_payload.get("task_class", {}).get("passed")
        and promoted_payload.get("artifact_contract", {}).get("candidate", {}).get("source") == "filesystem"
        and promoted_payload.get("resource_budget", {}).get("candidate", {}).get("total_tokens") == 1600
    )
    passed = route_only_rejected and strict_promoted
    detail = (
        "route-only stayed shadowed; strict task-class candidate used filesystem artifacts and event usage"
        if passed
        else f"route_only_rejected={route_only_rejected} strict_promoted={strict_promoted}"
    )
    return check_result(
        "long_session_gate_requires_strict_task_class_evidence",
        passed,
        detail,
        [str(route_only_path), str(promoted_path), str(candidate_root), str(candidate_events)],
    )


def run_gate(args: argparse.Namespace) -> int:
    sejong_root = Path(args.sejong_root).expanduser().resolve()
    repo_root = sejong_root.parents[1]
    work_dir = Path(args.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    outcome_check, quality_delta = outcome_quality_check(sejong_root, repo_root, work_dir)
    checks.append(outcome_check)
    checks.append(research_gate_check(sejong_root, repo_root, work_dir))
    checks.append(seungjeongwon_run_check(sejong_root, repo_root, work_dir))
    checks.append(team_persuasion_check(sejong_root, repo_root, work_dir))
    checks.append(feedback_contract_check(sejong_root))
    checks.append(product_evidence_check(sejong_root, repo_root))
    checks.append(long_session_gate_check(sejong_root, repo_root, work_dir))

    passed = all(check["passed"] for check in checks)
    payload = {
        "format": GATE_FORMAT,
        "generated_at": now_utc(),
        "goal": "tagback-growth",
        "passed": passed,
        "quality_delta": round(quality_delta, 4),
        "checks": checks,
        "work_dir": str(work_dir),
        "notes": [
            "This gate proves integration among current SOT guardrails and the added runtime-quality features.",
            "It does not prove real market success; production analytics or user evidence are still required.",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an integrated Sejong quality gate against latest SOT features.")
    parser.add_argument("--sejong-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--work-dir", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
