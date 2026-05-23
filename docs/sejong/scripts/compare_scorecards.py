#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RESOURCE_KEYS = (
    "total_tokens",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "tool_calls",
    "wall_time_sec",
    "estimated_cost_usd",
    "turn_count",
    "retry_count",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two King Sejong/Uigwe validation scorecards.")
    parser.add_argument("baseline", help="Baseline scorecard JSON path.")
    parser.add_argument("candidate", help="Candidate scorecard JSON path.")
    parser.add_argument("--require-non-regression", action="store_true", help="Exit non-zero if candidate regresses.")
    parser.add_argument("--max-token-ratio", type=float, default=None, help="Optional maximum allowed candidate/baseline token ratio.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resource(scorecard: dict[str, Any]) -> dict[str, float]:
    payload = scorecard.get("resource_usage") or {}
    return {key: float(payload.get(key, 0)) for key in RESOURCE_KEYS}


def ratio(candidate_value: float, baseline_value: float) -> float | None:
    if baseline_value == 0:
        return None
    return candidate_value / baseline_value


def scenario_map(scorecard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["scenario_id"]: item for item in scorecard.get("scenario_results", [])}


def status_rank(status: str) -> int:
    return {"fail": 0, "partial": 1, "pass": 2}.get(status, -1)


def main() -> int:
    args = parse_args()
    baseline = load_json(Path(args.baseline))
    candidate = load_json(Path(args.candidate))

    baseline_score = float(baseline["aggregate"]["average_score"])
    candidate_score = float(candidate["aggregate"]["average_score"])
    quality_delta = candidate_score - baseline_score

    baseline_resource = resource(baseline)
    candidate_resource = resource(candidate)
    total_token_ratio = ratio(candidate_resource["total_tokens"], baseline_resource["total_tokens"])
    cost_ratio = ratio(candidate_resource["estimated_cost_usd"], baseline_resource["estimated_cost_usd"])
    normalized_gain = quality_delta / max(cost_ratio or 1.0, 1.0)

    baseline_scenarios = scenario_map(baseline)
    candidate_scenarios = scenario_map(candidate)
    common_ids = sorted(set(baseline_scenarios).intersection(candidate_scenarios))
    regressions: list[str] = []
    improvements: list[str] = []
    for scenario_id in sorted(set(baseline_scenarios) - set(candidate_scenarios)):
        regressions.append(f"{scenario_id}: missing in candidate")
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
    if total_token_ratio is None:
        print("token_ratio=undefined")
    else:
        print(f"token_ratio={total_token_ratio:.4f}")
    if cost_ratio is None:
        print("cost_ratio=undefined")
    else:
        print(f"cost_ratio={cost_ratio:.4f}")
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

    failed = bool(regressions) or quality_delta < 0
    if args.max_token_ratio is not None and total_token_ratio is not None and total_token_ratio > args.max_token_ratio:
        failed = True
        print(f"\nToken ratio exceeded max-token-ratio={args.max_token_ratio}.")

    if args.require_non_regression and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
