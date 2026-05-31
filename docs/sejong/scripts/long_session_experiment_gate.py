#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outcome_quality_evaluator import (
    result_failures,
    score_result,
    task_failures,
)


GATE_FORMAT = "sejong.long-session-experiment-gate/v0.1-draft"
ROUTE_SURFACES = (
    "sejong",
    "jangyeongsil",
    "jiphyeonjeon",
    "uigwe",
    "seungjeongwon",
    "sillok",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_event_usage(path: Path) -> dict[str, Any]:
    usage = {
        "total_tokens": 0,
        "tool_calls": 0,
        "turn_count": 0,
    }
    if not path.exists():
        return usage
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            payload = event.get("usage") or {}
            usage["turn_count"] += 1
            usage["total_tokens"] += int(payload.get("input_tokens") or 0)
            usage["total_tokens"] += int(payload.get("output_tokens") or 0)
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            usage["tool_calls"] += 1
    return usage


def with_event_usage(result: dict[str, Any], event_path: str | None) -> dict[str, Any]:
    if not event_path:
        return result
    updated = dict(result)
    updated["resource_usage"] = load_event_usage(Path(event_path))
    return updated


def canonical_route(item: Any) -> str:
    text = str(item)
    for surface in ROUTE_SURFACES:
        if (
            text == surface
            or text.startswith(f"{surface}-")
            or text.startswith(f"{surface}_")
            or text.startswith(f"{surface}:")
        ):
            return surface
    return text


def is_subsequence(required: list[str], observed: list[str]) -> bool:
    if not required:
        return True
    required = [canonical_route(item) for item in required]
    observed = [canonical_route(item) for item in observed]
    cursor = 0
    for item in observed:
        if item == required[cursor]:
            cursor += 1
            if cursor == len(required):
                return True
    return False


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def ratio(candidate_value: Any, baseline_value: Any) -> float | None:
    if not isinstance(candidate_value, (int, float)) or not isinstance(baseline_value, (int, float)):
        return None
    if baseline_value == 0:
        return None
    return round(float(candidate_value) / float(baseline_value), 4)


def evaluate_baseline_behavior(task: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    requirements = task.get("baseline_requirements") or {}
    required_route = as_string_list(requirements.get("required_route_sequence"))
    forbidden_route = as_string_list(requirements.get("forbidden_route_sequence"))
    observed_route = as_string_list(baseline.get("route_sequence"))

    missing: list[str] = []
    if required_route and not is_subsequence(required_route, observed_route):
        missing.append("required baseline route sequence")
    if forbidden_route and is_subsequence(forbidden_route, observed_route):
        missing.append("forbidden long-session route sequence")

    return {
        "passed": not missing,
        "required_route_sequence": required_route,
        "forbidden_route_sequence": forbidden_route,
        "observed_route_sequence": observed_route,
        "missing": missing,
    }


def evaluate_intended_behavior(task: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    requirements = task.get("long_session_requirements") or {}
    required_route = as_string_list(requirements.get("required_route_sequence"))
    observed_route = as_string_list(candidate.get("route_sequence"))
    required_terminal_state = requirements.get("required_terminal_state")
    allowed_terminal_states = as_string_list(requirements.get("allowed_terminal_states"))
    if required_terminal_state and not allowed_terminal_states:
        allowed_terminal_states = [str(required_terminal_state)]
    observed_terminal_state = candidate.get("terminal_state")
    required_evidence = as_string_list(requirements.get("required_evidence"))
    evidence = candidate.get("long_session_evidence") or {}

    missing: list[str] = []
    if not is_subsequence(required_route, observed_route):
        missing.append("required route sequence")
    if allowed_terminal_states and observed_terminal_state not in allowed_terminal_states:
        missing.append("required terminal state")
    missing.extend(item for item in required_evidence if not evidence.get(item))

    return {
        "passed": not missing,
        "required_route_sequence": required_route,
        "observed_route_sequence": observed_route,
        "required_terminal_state": required_terminal_state,
        "allowed_terminal_states": allowed_terminal_states,
        "observed_terminal_state": observed_terminal_state,
        "missing": missing,
    }


def evaluate_task_class(task: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    expected = optional_string(task.get("task_class"))
    baseline_class = optional_string(baseline.get("task_class"))
    candidate_class = optional_string(candidate.get("task_class"))

    missing: list[str] = []
    if expected:
        if baseline_class != expected:
            missing.append("baseline task class does not match task")
        if candidate_class != expected:
            missing.append("candidate task class does not match task")
        evidence = candidate.get("long_session_evidence") if isinstance(candidate.get("long_session_evidence"), dict) else {}
        if expected == "code-review-defect-analysis" and not evidence.get("defect_first_critic"):
            missing.append("defect-first critic evidence missing for code-review-defect-analysis")
    elif baseline_class and candidate_class and baseline_class != candidate_class:
        missing.append("baseline and candidate task classes differ")

    return {
        "passed": not missing,
        "task_class": expected,
        "baseline_task_class": baseline_class,
        "candidate_task_class": candidate_class,
        "missing": missing,
    }


def paths_from_evidence(result: dict[str, Any]) -> set[str]:
    evidence = result.get("artifact_evidence") or {}
    paths: set[str] = set()
    for key in ("created_paths", "verified_paths"):
        paths.update(as_string_list(evidence.get(key)))
    return paths


def evaluate_artifact_contract(
    task: dict[str, Any],
    result: dict[str, Any],
    root: Path | None,
) -> dict[str, Any]:
    contract = task.get("artifact_contract") or {}
    required_paths = as_string_list(contract.get("required_paths"))
    forbidden_paths = as_string_list(contract.get("forbidden_paths"))
    required_checks = as_string_list(contract.get("required_checks"))
    required_markers = contract.get("required_markers") or []
    evidence = result.get("artifact_evidence") or {}
    checks = evidence.get("checks") if isinstance(evidence, dict) else {}
    checks = checks if isinstance(checks, dict) else {}

    missing_required_paths: list[str] = []
    present_forbidden_paths: list[str] = []
    observed_paths = sorted(paths_from_evidence(result))
    source = "result_evidence"

    if root is not None:
        source = "filesystem"
        for path in required_paths:
            if not (root / path).exists():
                missing_required_paths.append(path)
        for path in forbidden_paths:
            if (root / path).exists():
                present_forbidden_paths.append(path)
    else:
        for path in required_paths:
            if path not in observed_paths:
                missing_required_paths.append(path)
        for path in forbidden_paths:
            if path in observed_paths:
                present_forbidden_paths.append(path)

    missing_checks = [check for check in required_checks if not checks.get(check)]
    missing_markers: list[str] = []
    marker_results: list[dict[str, Any]] = []
    if root is not None:
        for group in required_markers:
            if not isinstance(group, dict):
                continue
            path = str(group.get("path") or "")
            markers = as_string_list(group.get("markers"))
            artifact_path = root / path
            if not path or not markers:
                continue
            if not artifact_path.exists():
                missing_markers.extend(f"{path}: {marker}" for marker in markers)
                marker_results.append({"path": path, "missing_markers": markers})
                continue
            text = artifact_path.read_text(encoding="utf-8", errors="replace")
            missing_for_path = [marker for marker in markers if marker not in text]
            missing_markers.extend(f"{path}: {marker}" for marker in missing_for_path)
            marker_results.append({"path": path, "missing_markers": missing_for_path})
    missing = (
        [f"missing required path: {path}" for path in missing_required_paths]
        + [f"forbidden path present: {path}" for path in present_forbidden_paths]
        + [f"missing required check: {check}" for check in missing_checks]
        + [f"missing required marker: {marker}" for marker in missing_markers]
    )

    return {
        "passed": not missing,
        "source": source,
        "required_paths": required_paths,
        "forbidden_paths": forbidden_paths,
        "required_checks": required_checks,
        "required_markers": required_markers,
        "observed_paths": observed_paths,
        "marker_results": marker_results,
        "missing": missing,
    }


def recompute_quality_scores(
    dimension_scores: dict[str, dict[str, Any]],
) -> tuple[float, float, dict[str, dict[str, Any]]]:
    total_weight = 0.0
    baseline_weighted_score = 0.0
    candidate_weighted_score = 0.0
    for scores in dimension_scores.values():
        weight = float(scores["baseline"]["weight"])
        total_weight += weight
        baseline_weighted_score += float(scores["baseline"]["score"]) * weight
        candidate_weighted_score += float(scores["candidate"]["score"]) * weight
        scores["delta"] = round(float(scores["candidate"]["score"]) - float(scores["baseline"]["score"]), 4)
    return (
        round(baseline_weighted_score / total_weight, 4),
        round(candidate_weighted_score / total_weight, 4),
        dimension_scores,
    )


def evaluate_outcome_quality(
    task: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    min_delta: float,
    artifact_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_score, baseline_dimensions = score_result(task, baseline)
    candidate_score, candidate_dimensions = score_result(task, candidate)
    dimension_scores = {
        dimension_id: {
            "baseline": baseline_dimensions[dimension_id],
            "candidate": candidate_dimensions[dimension_id],
            "delta": round(
                candidate_dimensions[dimension_id]["score"] - baseline_dimensions[dimension_id]["score"],
                4,
            ),
        }
        for dimension_id in baseline_dimensions
    }
    if artifact_contract and "artifact_contract" in dimension_scores:
        contract = task.get("artifact_contract") or {}
        required_checks = as_string_list(contract.get("required_checks"))
        for side in ("baseline", "candidate"):
            passed = bool(artifact_contract[side]["passed"])
            dimension_scores["artifact_contract"][side] = {
                "score": 1.0 if passed else 0.0,
                "weight": dimension_scores["artifact_contract"][side]["weight"],
                "passed_checks": required_checks if passed else [],
                "missing_checks": [] if passed else artifact_contract[side]["missing"],
            }
        baseline_score, candidate_score, dimension_scores = recompute_quality_scores(dimension_scores)
    score_delta = round(candidate_score - baseline_score, 4)
    return {
        "passed": score_delta >= min_delta and candidate_score > baseline_score,
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "score_delta": score_delta,
        "min_delta": min_delta,
        "dimension_scores": dimension_scores,
    }


def evaluate_resource_budget(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    max_token_ratio: float | None,
    max_tool_call_ratio: float | None,
) -> dict[str, Any]:
    baseline_usage = baseline.get("resource_usage") or {}
    candidate_usage = candidate.get("resource_usage") or {}
    token_ratio = ratio(candidate_usage.get("total_tokens"), baseline_usage.get("total_tokens"))
    tool_call_ratio = ratio(candidate_usage.get("tool_calls"), baseline_usage.get("tool_calls"))

    blockers: list[str] = []
    if max_token_ratio is not None and token_ratio is not None and token_ratio > max_token_ratio:
        blockers.append("token ratio exceeds budget")
    if max_tool_call_ratio is not None and tool_call_ratio is not None and tool_call_ratio > max_tool_call_ratio:
        blockers.append("tool call ratio exceeds budget")

    return {
        "passed": not blockers,
        "baseline": baseline_usage,
        "candidate": candidate_usage,
        "token_ratio": token_ratio,
        "tool_call_ratio": tool_call_ratio,
        "max_token_ratio": max_token_ratio,
        "max_tool_call_ratio": max_tool_call_ratio,
        "blockers": blockers,
    }


def promotion_proof_failures(args: argparse.Namespace, task: dict[str, Any]) -> list[str]:
    if not args.require_promotion:
        return []
    failures: list[str] = []
    if not optional_string(task.get("task_class")):
        failures.append("promotion proof requires task.task_class")
    for flag, value in (
        ("--baseline-root", args.baseline_root),
        ("--candidate-root", args.candidate_root),
        ("--baseline-events", args.baseline_events),
        ("--candidate-events", args.candidate_events),
    ):
        if not value:
            failures.append(f"promotion proof requires {flag}")
    return failures


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    task = load_json(Path(args.task))
    baseline = with_event_usage(load_json(Path(args.baseline)), args.baseline_events)
    candidate = with_event_usage(load_json(Path(args.candidate)), args.candidate_events)

    failures = task_failures(task)
    failures.extend(result_failures(task, baseline, "baseline"))
    failures.extend(result_failures(task, candidate, "candidate"))
    failures.extend(promotion_proof_failures(args, task))
    if failures:
        return {}, failures

    min_delta = float(args.min_delta if args.min_delta is not None else task.get("min_promote_delta", 0.0))
    baseline_root = Path(args.baseline_root) if args.baseline_root else None
    candidate_root = Path(args.candidate_root) if args.candidate_root else None
    task_class = evaluate_task_class(task, baseline, candidate)
    baseline_behavior = evaluate_baseline_behavior(task, baseline)
    intended_behavior = evaluate_intended_behavior(task, candidate)
    artifact_contract = {
        "baseline": evaluate_artifact_contract(task, baseline, baseline_root),
        "candidate": evaluate_artifact_contract(task, candidate, candidate_root),
    }
    outcome_quality = evaluate_outcome_quality(task, baseline, candidate, min_delta, artifact_contract)
    resource_budget = evaluate_resource_budget(
        baseline,
        candidate,
        args.max_token_ratio,
        args.max_tool_call_ratio,
    )

    blockers: list[str] = []
    if not task_class["passed"]:
        blockers.extend(task_class["missing"])
    if not baseline_behavior["passed"]:
        blockers.append("baseline is not current Sejong behavior")
    if not intended_behavior["passed"]:
        blockers.append("intended long-session behavior is incomplete")
    if not artifact_contract["candidate"]["passed"]:
        blockers.append("candidate artifact contract is incomplete")
    if not outcome_quality["passed"]:
        blockers.append("outcome quality delta is below promotion threshold")
    if not resource_budget["passed"]:
        blockers.extend(resource_budget["blockers"])

    recommendation = "promote_candidate" if not blockers else "keep_shadowing"
    payload = {
        "format": GATE_FORMAT,
        "generated_at": now_utc(),
        "task_id": task["task_id"],
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "task_class": task_class,
        "baseline_behavior": baseline_behavior,
        "intended_behavior": intended_behavior,
        "artifact_contract": artifact_contract,
        "outcome_quality": outcome_quality,
        "resource_budget": resource_budget,
        "recommendation": recommendation,
        "blockers": blockers,
        "notes": [
            "Promotion requires intended behavior, better result quality, and acceptable overhead.",
            "This gate promotes a behavior candidate for shadow or live trials; it does not prove product success.",
        ],
    }
    return payload, []


def judge(args: argparse.Namespace) -> int:
    payload, failures = build_payload(args)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1

    if args.write:
        Path(args.write).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_promotion and payload["recommendation"] != "promote_candidate":
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Judge whether a long-session Sejong candidate merits promotion.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    judge_parser = subparsers.add_parser("judge", help="Judge a baseline and candidate against a long-session task.")
    judge_parser.add_argument("--task", required=True)
    judge_parser.add_argument("--baseline", required=True)
    judge_parser.add_argument("--candidate", required=True)
    judge_parser.add_argument("--min-delta", type=float)
    judge_parser.add_argument("--max-token-ratio", type=float)
    judge_parser.add_argument("--max-tool-call-ratio", type=float)
    judge_parser.add_argument("--baseline-root")
    judge_parser.add_argument("--candidate-root")
    judge_parser.add_argument("--baseline-events")
    judge_parser.add_argument("--candidate-events")
    judge_parser.add_argument("--write")
    judge_parser.add_argument("--require-promotion", action="store_true")
    judge_parser.set_defaults(func=judge)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
