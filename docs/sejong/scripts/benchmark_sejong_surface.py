#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SEJONG_ROOT = SCRIPT_PATH.parents[1]
TASK_SET_PATH = SEJONG_ROOT / "examples" / "validation" / "sejong-seed-task-set.json"
SCORECARD_PATH = SEJONG_ROOT / "examples" / "validation" / "runs" / "sejong-surface.scorecard.json"
SUMMARY_PATH = SEJONG_ROOT / "examples" / "validation" / "runs" / "sejong-surface.scorecard.md"

VALID_SURFACES = {
    "sejong",
    "jangyeongsil",
    "jiphyeonjeon",
    "uigwe",
    "seungjeongwon",
    "sillok",
    "danjong",
    "sejong-direct",
}

REQUIRED_PROFILES = {
    "routing": 5,
    "research": 2,
    "decision": 2,
    "planning": 3,
    "execution": 2,
    "team": 2,
    "guardrail": 3,
    "continuity": 2,
    "sejong": 1,
}

REQUIRED_SCENARIO_IDS = {
    "route-evidence-only-history",
    "route-option-comparison",
    "route-vague-product-plan",
    "route-approved-bundle-execution",
    "route-clear-direct-task",
    "route-material-self-modification",
    "repo-context-refresh-candidate-first",
    "research-stale-external-facts",
    "research-repo-fanout",
    "research-to-uigwe-promotion-gate",
    "decision-skill-plugin-boundary",
    "decision-expansion-roi",
    "planning-greenfield-full",
    "planning-design-to-plan",
    "planning-decompose-only",
    "execution-small-doc-fix",
    "execution-validated-leaf",
    "team-jiphyeonjeon-challenge-round",
    "team-execution-disjoint-leases",
    "hook-protected-path-route-gate",
    "hook-subagent-final-claim",
    "continuity-follow-up-same-workflow",
    "continuity-compaction-pending-gate",
    "continuity-ambiguity-register-open-item",
    "chain-research-plan-execute-record",
    "chain-tagback-growth-goal-backed",
    "efficiency-direct-overhead-budget",
}

RESOURCE_FIELDS = {
    "max_turns",
    "max_tool_calls",
    "max_total_tokens",
    "overhead_budget_note",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark King Sejong seed surface coverage.")
    parser.add_argument("--task-set", default=str(TASK_SET_PATH), help="Sejong seed task set to load.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown scorecards.")
    parser.add_argument("--require-targets", action="store_true", help="Exit non-zero unless all target checks pass.")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, passed: bool, detail: str, *, missing: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": name,
        "passed": passed,
        "detail": detail,
    }
    if missing:
        payload["missing"] = missing
    return payload


def surfaces_from_scenario(scenario: dict[str, Any]) -> list[str]:
    surfaces: list[str] = []
    surfaces.extend(scenario.get("expected_route_sequence") or [])
    surfaces.extend(scenario.get("forbidden_surfaces") or [])
    for route in scenario.get("acceptable_route_sequences") or []:
        surfaces.extend(route)
    return surfaces


def evaluate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    route_sequence = scenario.get("expected_route_sequence") or []
    checks.append(
        check(
            "expected_route_sequence_present",
            bool(route_sequence),
            "Scenario names the primary expected Sejong route sequence.",
        )
    )

    acceptable_routes = scenario.get("acceptable_route_sequences") or []
    checks.append(
        check(
            "acceptable_route_sequences_present",
            bool(acceptable_routes),
            "Scenario names at least one acceptable route sequence.",
        )
    )

    invalid_surfaces = sorted({surface for surface in surfaces_from_scenario(scenario) if surface not in VALID_SURFACES})
    checks.append(
        check(
            "route_surfaces_valid",
            not invalid_surfaces,
            "All route and forbidden surface names are valid Sejong surfaces.",
            missing=invalid_surfaces,
        )
    )

    expected_behavior = scenario.get("expected_behavior") or []
    checks.append(
        check(
            "expected_behavior_present",
            len(expected_behavior) >= 2,
            "Scenario has concrete expected behavior bullets.",
        )
    )

    forbidden_behavior = scenario.get("forbidden_behavior") or []
    checks.append(
        check(
            "forbidden_behavior_present",
            len(forbidden_behavior) >= 2,
            "Scenario has concrete forbidden behavior bullets.",
        )
    )

    expected_artifacts = scenario.get("expected_artifacts") or []
    checks.append(
        check(
            "expected_artifacts_present",
            bool(expected_artifacts),
            "Scenario names observable artifacts or evidence to grade.",
        )
    )

    grading_notes = scenario.get("grading_notes") or []
    checks.append(
        check(
            "grading_notes_present",
            bool(grading_notes),
            "Scenario includes grading notes for human or LLM judge use.",
        )
    )

    resource_expectations = scenario.get("resource_expectations") or {}
    missing_resource_fields = sorted(RESOURCE_FIELDS - set(resource_expectations))
    checks.append(
        check(
            "resource_expectations_present",
            not missing_resource_fields,
            "Scenario records token, tool, turn, and overhead budget expectations.",
            missing=missing_resource_fields,
        )
    )

    profile = scenario.get("profile")
    needs_guardrail = profile in {"team", "guardrail", "continuity"}
    guardrail_expectations = scenario.get("guardrail_expectations") or {}
    checks.append(
        check(
            "guardrail_expectations_present_when_needed",
            bool(guardrail_expectations) or not needs_guardrail,
            "Scenarios with team, protected, continuity, or handoff risk name guardrail expectations.",
        )
    )

    passed_checks = sum(1 for item in checks if item["passed"])
    score = round(passed_checks / len(checks), 4)
    status = "pass" if score == 1 else "partial" if score >= 0.75 else "fail"
    if status == "fail":
        blockers.append("Scenario is missing required benchmark contract fields.")

    return {
        "scenario_id": scenario["id"],
        "title": scenario["title"],
        "status": status,
        "score": score,
        "checks": checks,
        "blockers": blockers,
        "notes": [
            f"profile={profile}",
            f"expected_route_sequence={','.join(route_sequence)}",
        ],
        "resource_usage": {
            "total_tokens": 0,
            "tool_calls": 0,
            "wall_time_sec": 0,
            "turn_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "estimated_cost_usd": 0,
            "retry_count": 0,
        },
    }


def evaluate_task_set(task_set: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    scenarios = task_set.get("scenarios") or []
    results = [evaluate_scenario(scenario) for scenario in scenarios]

    notes: list[str] = []
    scenario_ids = {scenario.get("id") for scenario in scenarios}
    missing_ids = sorted(REQUIRED_SCENARIO_IDS - scenario_ids)
    extra_ids = sorted(scenario_ids - REQUIRED_SCENARIO_IDS)
    if missing_ids:
        notes.append(f"missing required scenarios: {', '.join(missing_ids)}")
    if extra_ids:
        notes.append(f"extra scenarios present: {', '.join(extra_ids)}")

    profile_counts: dict[str, int] = {}
    for scenario in scenarios:
        profile = scenario.get("profile")
        profile_counts[profile] = profile_counts.get(profile, 0) + 1
    for profile, minimum in REQUIRED_PROFILES.items():
        count = profile_counts.get(profile, 0)
        if count < minimum:
            notes.append(f"profile {profile} below target: {count}/{minimum}")

    return results, notes


def aggregate(results: list[dict[str, Any]], notes: list[str]) -> dict[str, Any]:
    pass_count = sum(1 for result in results if result["status"] == "pass")
    partial_count = sum(1 for result in results if result["status"] == "partial")
    fail_count = sum(1 for result in results if result["status"] == "fail")
    average_score = round(sum(result["score"] for result in results) / len(results), 4)
    return {
        "scenario_count": len(results),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "fail_count": fail_count,
        "average_score": average_score,
        "meets_targets": fail_count == 0 and partial_count == 0 and not notes,
    }


def build_scorecard(task_set: dict[str, Any], results: list[dict[str, Any]], notes: list[str]) -> dict[str, Any]:
    return {
        "format": "uigwe.validation-scorecard/v0.1-draft",
        "metadata": {
            "id": "sejong-surface-scorecard",
            "task_set_id": task_set["metadata"]["id"],
            "generated_at": now_utc_iso(),
            "system_under_test": "sejong-surface",
            "runner": "benchmark_sejong_surface.py",
        },
        "aggregate": aggregate(results, notes),
        "scenario_results": results,
        "resource_usage": {
            "total_tokens": 0,
            "tool_calls": 0,
            "wall_time_sec": 0,
            "turn_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "estimated_cost_usd": 0,
            "retry_count": 0,
        },
        "notes": notes or [
            "Deterministic seed-surface benchmark; resource usage is zero because no model run is executed."
        ],
    }


def preserve_generated_at_when_unchanged(scorecard: dict[str, Any], existing_path: Path) -> dict[str, Any]:
    if not existing_path.exists():
        return scorecard
    try:
        existing = load_json(existing_path)
    except Exception:
        return scorecard

    existing_generated_at = existing.get("metadata", {}).get("generated_at")
    candidate = json.loads(json.dumps(scorecard))
    if existing_generated_at:
        candidate.setdefault("metadata", {})["generated_at"] = existing_generated_at
    if candidate == existing:
        scorecard["metadata"]["generated_at"] = existing_generated_at
    return scorecard


def write_outputs(scorecard: dict[str, Any]) -> None:
    scorecard = preserve_generated_at_when_unchanged(scorecard, SCORECARD_PATH)
    SCORECARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD_PATH.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# King Sejong Surface Scorecard",
        "",
        f"- Task set: `{scorecard['metadata']['task_set_id']}`",
        f"- Generated at: `{scorecard['metadata']['generated_at']}`",
        f"- Status: `{'pass' if scorecard['aggregate']['meets_targets'] else 'fail'}`",
        f"- Average score: `{scorecard['aggregate']['average_score']}`",
        f"- Pass/partial/fail: `{scorecard['aggregate']['pass_count']}/{scorecard['aggregate']['partial_count']}/{scorecard['aggregate']['fail_count']}`",
        "",
        "## Scenarios",
    ]
    for result in scorecard["scenario_results"]:
        lines.append(f"- `{result['scenario_id']}`: `{result['status']}` ({result['score']})")
    lines.append("")
    if scorecard["notes"]:
        lines.append("## Notes")
        for note in scorecard["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    task_set = load_json(Path(args.task_set))
    results, notes = evaluate_task_set(task_set)
    scorecard = build_scorecard(task_set, results, notes)

    if args.write:
        write_outputs(scorecard)

    print(f"task_set={scorecard['metadata']['task_set_id']}")
    print(f"scenarios={scorecard['aggregate']['scenario_count']}")
    print(
        "pass/partial/fail="
        f"{scorecard['aggregate']['pass_count']}/"
        f"{scorecard['aggregate']['partial_count']}/"
        f"{scorecard['aggregate']['fail_count']}"
    )
    print(f"average_score={scorecard['aggregate']['average_score']}")
    print(f"meets_targets={scorecard['aggregate']['meets_targets']}")
    for note in notes:
        print(f"note: {note}")

    if args.require_targets and not scorecard["aggregate"]["meets_targets"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
