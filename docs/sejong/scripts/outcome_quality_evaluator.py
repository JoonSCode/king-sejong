#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_FORMAT = "sejong.outcome-quality-task/v0.1-draft"
RESULT_FORMAT = "sejong.outcome-quality-result/v0.1-draft"
COMPARISON_FORMAT = "sejong.outcome-quality-comparison/v0.1-draft"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def result_failures(task: dict[str, Any], result: dict[str, Any], label: str) -> list[str]:
    failures: list[str] = []
    if result.get("format") != RESULT_FORMAT:
        failures.append(f"{label} has unexpected format: {result.get('format')}")
    dimensions = result.get("dimensions")
    if not isinstance(dimensions, dict):
        failures.append(f"{label} dimensions must be an object")
        dimensions = {}
    for dimension in task.get("required_dimensions") or []:
        dimension_id = dimension.get("id")
        if not dimension_id:
            failures.append("task required dimension missing id")
            continue
        if dimension_id not in dimensions:
            failures.append(f"{label} missing required dimension: {dimension_id}")
            continue
        payload = dimensions.get(dimension_id)
        if not isinstance(payload, dict):
            failures.append(f"{label} dimension must be an object: {dimension_id}")
    return failures


def task_failures(task: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if task.get("format") != TASK_FORMAT:
        failures.append(f"task has unexpected format: {task.get('format')}")
    dimensions = task.get("required_dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        failures.append("task requires at least one required_dimension")
        return failures
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            failures.append("required_dimension must be an object")
            continue
        if not dimension.get("id"):
            failures.append("required_dimension missing id")
        weight = dimension.get("weight")
        if not isinstance(weight, (int, float)) or weight <= 0:
            failures.append(f"required_dimension has invalid weight: {dimension.get('id')}")
        checks = dimension.get("checks")
        if not isinstance(checks, list) or not checks:
            failures.append(f"required_dimension has no checks: {dimension.get('id')}")
    return failures


def score_result(task: dict[str, Any], result: dict[str, Any]) -> tuple[float, dict[str, dict[str, Any]]]:
    total_weight = 0.0
    weighted_score = 0.0
    dimension_scores: dict[str, dict[str, Any]] = {}
    dimensions = result.get("dimensions") or {}
    for dimension in task.get("required_dimensions") or []:
        dimension_id = str(dimension["id"])
        weight = float(dimension["weight"])
        checks = [str(check) for check in dimension["checks"]]
        payload = dimensions.get(dimension_id) or {}
        passed = [check for check in checks if is_present(payload.get(check))]
        missing = [check for check in checks if check not in passed]
        score = len(passed) / len(checks)
        total_weight += weight
        weighted_score += score * weight
        dimension_scores[dimension_id] = {
            "score": round(score, 4),
            "weight": weight,
            "passed_checks": passed,
            "missing_checks": missing,
        }
    return round(weighted_score / total_weight, 4), dimension_scores


def compare(args: argparse.Namespace) -> int:
    task = load_json(Path(args.task))
    baseline = load_json(Path(args.baseline))
    candidate = load_json(Path(args.candidate))

    failures = task_failures(task)
    failures.extend(result_failures(task, baseline, "baseline"))
    failures.extend(result_failures(task, candidate, "candidate"))
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1

    baseline_score, baseline_dimensions = score_result(task, baseline)
    candidate_score, candidate_dimensions = score_result(task, candidate)
    delta = round(candidate_score - baseline_score, 4)
    min_delta = float(args.min_delta if args.min_delta is not None else task.get("min_promote_delta", 0.0))
    if candidate_score > baseline_score:
        winner = "candidate"
    elif baseline_score > candidate_score:
        winner = "baseline"
    else:
        winner = "tie"
    if winner == "candidate" and delta >= min_delta:
        recommendation = "promote_candidate"
    elif winner == "candidate":
        recommendation = "keep_shadowing"
    elif winner == "tie":
        recommendation = "inconclusive"
    else:
        recommendation = "reject_candidate"

    dimension_scores: dict[str, dict[str, Any]] = {}
    for dimension_id in baseline_dimensions:
        dimension_scores[dimension_id] = {
            "baseline": baseline_dimensions[dimension_id],
            "candidate": candidate_dimensions[dimension_id],
            "delta": round(
                candidate_dimensions[dimension_id]["score"] - baseline_dimensions[dimension_id]["score"],
                4,
            ),
        }

    payload = {
        "format": COMPARISON_FORMAT,
        "generated_at": now_utc(),
        "task_id": task["task_id"],
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "score_delta": delta,
        "min_promote_delta": min_delta,
        "winner": winner,
        "recommendation": recommendation,
        "dimension_scores": dimension_scores,
        "notes": [
            "Scores compare structured outcome artifacts against the same task-specific checks.",
            "This deterministic grader does not replace human or live A/B validation for real product success.",
        ],
    }
    if args.write:
        Path(args.write).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if recommendation == "promote_candidate" or not args.require_promotion else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare Sejong outcome artifacts against task-specific quality checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare_parser = subparsers.add_parser("compare", help="Compare a baseline and candidate outcome result.")
    compare_parser.add_argument("--task", required=True)
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--candidate", required=True)
    compare_parser.add_argument("--min-delta", type=float)
    compare_parser.add_argument("--write")
    compare_parser.add_argument("--require-promotion", action="store_true")
    compare_parser.set_defaults(func=compare)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
