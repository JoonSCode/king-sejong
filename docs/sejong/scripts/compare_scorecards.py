#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


class ComparisonError(ValueError):
    """The requested comparison has invalid or incomparable inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two King Sejong/Uigwe validation scorecards.")
    parser.add_argument("baseline", help="Baseline scorecard JSON path.")
    parser.add_argument("candidate", help="Candidate scorecard JSON path.")
    parser.add_argument("--require-non-regression", action="store_true", help="Exit non-zero if candidate regresses.")
    parser.add_argument("--max-token-ratio", type=float, default=None, help="Optional maximum allowed candidate/baseline token ratio.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any, label: str, *, integer: bool = False) -> float | int:
    if (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or (integer and not isinstance(value, int))
        or not math.isfinite(value) or value < 0
    ):
        raise ComparisonError(f"{label} must be a finite non-negative {'integer' if integer else 'number'}")
    return value


def resource(scorecard: dict[str, Any]) -> dict[str, float | int | None]:
    payload = scorecard.get("resource_usage", {})
    if not isinstance(payload, dict):
        raise ComparisonError("resource_usage must be an object")
    result: dict[str, float | int | None] = {}
    for key in ("total_tokens", "estimated_cost_usd"):
        result[key] = number(payload[key], key, integer=key == "total_tokens") if key in payload else None
    return result


def ratio(candidate_value: float | int | None, baseline_value: float | int | None) -> float | None:
    if candidate_value is None or baseline_value is None or baseline_value == 0:
        return None
    return candidate_value / baseline_value


def scenario_map(scorecard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = scorecard["scenario_results"]
    if not isinstance(results, list) or not results:
        raise ComparisonError("scenario_results must be a non-empty array")
    scenarios: dict[str, dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict):
            raise ComparisonError("each scenario must be an object")
        scenario_id = item["scenario_id"]
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ComparisonError("scenario_id must be non-empty text")
        if scenario_id in scenarios:
            raise ComparisonError(f"duplicate scenario_id: {scenario_id}")
        if item["status"] not in ("fail", "partial", "pass"):
            raise ComparisonError(f"invalid scenario status: {scenario_id}")
        if number(item["score"], f"score of {scenario_id}") > 1:
            raise ComparisonError(f"scenario score exceeds 1: {scenario_id}")
        scenarios[scenario_id] = item
    aggregate = scorecard["aggregate"]
    if not isinstance(aggregate, dict):
        raise ComparisonError("aggregate must be an object")
    counts = {"scenario_count": len(results)}
    counts.update({f"{status}_count": sum(item["status"] == status for item in results)
                   for status in ("pass", "partial", "fail")})
    for key, expected in counts.items():
        if number(aggregate[key], key, integer=True) != expected:
            raise ComparisonError(f"aggregate {key} disagrees with scenarios")
    # Both existing surface benchmark generators round the mean to four places.
    expected_average = round(sum(item["score"] for item in results) / len(results), 4)
    if number(aggregate["average_score"], "average_score") != expected_average:
        raise ComparisonError("aggregate average_score disagrees with scenarios")
    return scenarios


def identity(scorecard: dict[str, Any]) -> str:
    for key in ("id", "task_set_id"):
        value = scorecard["metadata"][key]
        if not isinstance(value, str) or not value.strip():
            raise ComparisonError(f"metadata {key} must be non-empty text")
    return scorecard["metadata"]["task_set_id"]


def print_ratio(label: str, value: float | None, resources: tuple[float | int | None, ...]) -> None:
    if any(item is None for item in resources):
        print(f"{label}=unknown")
    elif value is None:
        print(f"{label}=undefined")
    else:
        print(f"{label}={value:.4f}")


def status_rank(status: str) -> int:
    return {"fail": 0, "partial": 1, "pass": 2}.get(status, -1)


def compare(args: argparse.Namespace) -> int:
    baseline = load_json(Path(args.baseline))
    candidate = load_json(Path(args.candidate))

    if args.max_token_ratio is not None:
        number(args.max_token_ratio, "max-token-ratio")
    if identity(baseline) != identity(candidate):
        raise ComparisonError("task_set_id must match")
    baseline_scenarios = scenario_map(baseline)
    candidate_scenarios = scenario_map(candidate)
    if set(baseline_scenarios) != set(candidate_scenarios):
        raise ComparisonError("scenario ID sets must match")

    baseline_score = float(baseline["aggregate"]["average_score"])
    candidate_score = float(candidate["aggregate"]["average_score"])
    quality_delta = candidate_score - baseline_score

    baseline_resource = resource(baseline)
    candidate_resource = resource(candidate)
    total_token_ratio = ratio(candidate_resource["total_tokens"], baseline_resource["total_tokens"])
    cost_ratio = ratio(candidate_resource["estimated_cost_usd"], baseline_resource["estimated_cost_usd"])
    normalized_gain = None if cost_ratio is None else quality_delta / max(cost_ratio, 1.0)

    common_ids = sorted(baseline_scenarios)
    regressions: list[str] = []
    improvements: list[str] = []
    for scenario_id in common_ids:
        before = baseline_scenarios[scenario_id]
        after = candidate_scenarios[scenario_id]
        before_status = before["status"]
        after_status = after["status"]
        before_score = float(before["score"])
        after_score = float(after["score"])
        if status_rank(after_status) < status_rank(before_status) or after_score < before_score:
            regressions.append(f"{scenario_id}: {before_status}/{before_score} -> {after_status}/{after_score}")
        elif status_rank(after_status) > status_rank(before_status) or after_score > before_score:
            improvements.append(f"{scenario_id}: {before_status}/{before_score} -> {after_status}/{after_score}")

    print("# Scorecard Comparison")
    print(f"baseline={baseline['metadata']['id']} ({baseline['metadata']['task_set_id']})")
    print(f"candidate={candidate['metadata']['id']} ({candidate['metadata']['task_set_id']})")
    print(f"baseline_average={baseline_score}")
    print(f"candidate_average={candidate_score}")
    print(f"quality_delta={quality_delta:+.4f}")
    print_ratio("token_ratio", total_token_ratio,
                (candidate_resource["total_tokens"], baseline_resource["total_tokens"]))
    print_ratio("cost_ratio", cost_ratio,
                (candidate_resource["estimated_cost_usd"], baseline_resource["estimated_cost_usd"]))
    if normalized_gain is None:
        print("cost_normalized_gain=unknown")
    else:
        print(f"cost_normalized_gain={normalized_gain:+.4f}")
    print(f"scenario_improvements={len(improvements)}")
    print(f"scenario_regressions={len(regressions)}")

    if improvements:
        print("\n## Improvements")
        for item in improvements:
            print(f"- {item}")
    if regressions:
        print("\n## Regressions")
        for item in regressions:
            print(f"- {item}")

    if args.max_token_ratio is not None:
        if total_token_ratio is None:
            print("\nToken ratio cannot be checked against max-token-ratio: unknown or undefined usage.")
            return 1
        if total_token_ratio > args.max_token_ratio:
            print(f"\nToken ratio exceeded max-token-ratio={args.max_token_ratio}.")
            return 1
    return int(args.require_non_regression and (bool(regressions) or quality_delta < 0))


def main() -> int:
    args = parse_args()
    try:
        return compare(args)
    except (ComparisonError, OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"Invalid comparison: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
