#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from copy import deepcopy
from typing import Any, Callable

from benchmark_workflow_run import invalid_cases, large_run, valid_cases
from sejong_workflow_run import BACKENDS, MODES, RECOMMENDATIONS, RUN_FORMAT, SURFACES, WORKFLOW_KINDS, reviewable_ref, run_failures


MIN_SCORE_DELTA = 0.10
MIN_MULTI_METRIC_SCORE = 0.90
MAX_LARGE_LEDGER_SECONDS = 1.0
DIMENSION_WEIGHTS = {
    "promotion_decision_quality": 0.35,
    "outcome_quality": 0.20,
    "efficiency_cost": 0.10,
    "parallelism_efficiency": 0.10,
    "reliability_reproducibility": 0.10,
    "observability_diagnosability": 0.10,
    "human_developer_experience": 0.05,
}
DIMENSION_MINIMUMS = {
    "promotion_decision_quality": 1.00,
    "outcome_quality": 0.90,
    "efficiency_cost": 0.60,
    "parallelism_efficiency": 1.00,
    "reliability_reproducibility": 1.00,
    "observability_diagnosability": 0.90,
    "human_developer_experience": 0.90,
}
REQUIRED_MATRIX_CASE_IDS = {
    "weak-positive-delta-promotion",
    "promotion-without-approval",
    "empty-acceptance-criteria",
    "final-recommendation-mismatch",
    "high-overhead-weak-promotion",
    "overlapping-write-scopes",
    "duplicate-worker-and-evidence",
    "invalid-timestamp-and-extra-field",
    "missing-artifact-storage",
    "missing-metrics",
    "weak-other-provenance",
    "manual-shadow-promoted",
}


def baseline_lightweight_failures(data: dict[str, Any]) -> list[str]:
    """Approximate the pre-hardening ledger check for deterministic comparison."""
    failures: list[str] = []
    required = [
        "format",
        "run_id",
        "repo_root",
        "status",
        "workflow_kind",
        "workflow_name",
        "mapped_surfaces",
        "backend",
        "mode",
        "source_of_truth_refs",
        "success_criteria",
        "workers",
        "evidence_ledger",
        "quality_comparison",
        "verification_evidence",
        "violations",
        "final_recommendation",
    ]
    for field in required:
        if field not in data:
            failures.append(f"missing {field}")
    if data.get("format") != RUN_FORMAT:
        failures.append(f"unexpected format: {data.get('format')}")
    if data.get("workflow_kind") not in WORKFLOW_KINDS:
        failures.append(f"unsupported workflow kind: {data.get('workflow_kind')}")
    if data.get("backend") not in BACKENDS:
        failures.append(f"unsupported backend: {data.get('backend')}")
    if data.get("mode") not in MODES:
        failures.append(f"unsupported mode: {data.get('mode')}")
    if data.get("final_recommendation") not in RECOMMENDATIONS:
        failures.append(f"unsupported final recommendation: {data.get('final_recommendation')}")
    for surface in data.get("mapped_surfaces") or []:
        if surface not in SURFACES:
            failures.append(f"unsupported mapped surface: {surface}")

    comparison = data.get("quality_comparison") if isinstance(data.get("quality_comparison"), dict) else {}
    if data.get("mode") == "promoted_backend" and data.get("final_recommendation") != "promote":
        failures.append("promoted_backend mode requires final_recommendation promote")
    if data.get("final_recommendation") == "promote":
        if comparison.get("recommendation") != "promote":
            failures.append("promote requires quality_comparison recommendation promote")
        if comparison.get("outcome_quality_delta", 0) <= 0:
            failures.append("promote requires positive outcome_quality_delta")
        if data.get("violations"):
            failures.append("promote requires no violations")
    if data.get("status") == "completed":
        if not data.get("verification_evidence"):
            failures.append("completed run requires verification evidence")
        if data.get("final_recommendation") == "unknown":
            failures.append("completed run requires a non-unknown final recommendation")
        if comparison.get("recommendation") == "unknown":
            failures.append("completed run requires quality comparison recommendation")
        if comparison.get("baseline_result_ref") == "unrecorded" or comparison.get("candidate_result_ref") == "unrecorded":
            failures.append("completed run requires baseline and candidate result refs")
    return failures


def curated_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for data in valid_cases():
        cases.append(
            {
                "id": data["run_id"],
                "expect": "valid",
                "data": data,
                "expected_fragments": [],
            }
        )
    for data, expected_fragments in invalid_cases():
        cases.append(
            {
                "id": data["run_id"],
                "expect": "invalid",
                "data": data,
                "expected_fragments": expected_fragments,
            }
        )

    hidden_with_other = deepcopy(valid_cases()[1])
    hidden_with_other["run_id"] = "hidden-claude-through-other-fields"
    hidden_with_other["backend"] = "other"
    hidden_with_other["backend_provenance"] = {
        "migration_type": "approved_other",
        "non_claude_runtime": True,
        "summary": "Approved mock, but candidate ref leaks Claude CLI.",
        "command_refs": ["mock:approved-other"],
    }
    hidden_with_other["quality_comparison"]["candidate_result_ref"] = "Claude CLI generated candidate"
    cases.append(
        {
            "id": hidden_with_other["run_id"],
            "expect": "invalid",
            "data": hidden_with_other,
            "expected_fragments": ["hidden Claude runtime reference is forbidden"],
        }
    )

    repo_artifact_gap = deepcopy(valid_cases()[1])
    repo_artifact_gap["run_id"] = "missing-artifact-storage"
    repo_artifact_gap.pop("artifact_storage", None)
    cases.append(
        {
            "id": repo_artifact_gap["run_id"],
            "expect": "invalid",
            "data": repo_artifact_gap,
            "expected_fragments": ["missing artifact_storage"],
        }
    )

    missing_metrics = deepcopy(valid_cases()[1])
    missing_metrics["run_id"] = "missing-metrics"
    missing_metrics.pop("metrics", None)
    cases.append(
        {
            "id": missing_metrics["run_id"],
            "expect": "invalid",
            "data": missing_metrics,
            "expected_fragments": ["missing metrics"],
        }
    )

    invalid_timestamp = deepcopy(valid_cases()[1])
    invalid_timestamp["run_id"] = "invalid-timestamp-and-extra-field"
    invalid_timestamp["created_at"] = "not-a-date"
    invalid_timestamp["extra"] = "schema parity violation"
    cases.append(
        {
            "id": invalid_timestamp["run_id"],
            "expect": "invalid",
            "data": invalid_timestamp,
            "expected_fragments": ["created_at must be a date-time string", "unexpected top-level field"],
        }
    )
    return cases


def case_tags(case_id: str) -> set[str]:
    tags: set[str] = set()
    if case_id.startswith("hidden-claude"):
        tags.update({"critical", "hidden_runtime", "security"})
    if case_id in {"promote-with-violation", "high-overhead-weak-promotion", "weak-positive-delta-promotion", "promotion-without-approval", "final-recommendation-mismatch", "manual-shadow-promoted"}:
        tags.update({"critical", "promotion"})
    if case_id in {"other-without-provenance", "weak-other-provenance", "missing-artifact-storage", "missing-metrics"}:
        tags.update({"critical", "provenance"})
    if case_id == "empty-acceptance-criteria":
        tags.update({"critical", "outcome_quality"})
    if case_id in {"overlapping-write-scopes", "duplicate-worker-and-evidence"}:
        tags.update({"parallelism"})
    if case_id == "invalid-timestamp-and-extra-field":
        tags.update({"schema_parity", "reliability"})
    return tags


def score_case(failures: list[str], expected_fragments: list[str], expect: str) -> tuple[float, list[str]]:
    if expect == "valid":
        return (1.0, []) if not failures else (0.0, failures)
    if not failures:
        return 0.0, ["expected invalid case to fail, but it passed"]
    joined = "\n".join(failures)
    matched = [fragment for fragment in expected_fragments if fragment in joined]
    score = len(matched) / len(expected_fragments) if expected_fragments else 1.0
    missing = [fragment for fragment in expected_fragments if fragment not in joined]
    return score, missing


def evaluate_validator(name: str, validator: Callable[[dict[str, Any]], list[str]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    elapsed_values = []
    for case in cases:
        data = deepcopy(case["data"])
        started = time.perf_counter()
        failures = validator(data)
        elapsed = time.perf_counter() - started
        elapsed_values.append(elapsed)
        score, missing = score_case(failures, case["expected_fragments"], case["expect"])
        results.append(
            {
                "id": case["id"],
                "expect": case["expect"],
                "tags": sorted(case_tags(case["id"])),
                "score": round(score, 4),
                "passed": score == 1.0,
                "failures": failures,
                "missing_expected_fragments": missing,
                "elapsed_seconds": round(elapsed, 6),
            }
        )
    average_score = sum(item["score"] for item in results) / len(results)
    return {
        "name": name,
        "average_score": round(average_score, 4),
        "case_count": len(results),
        "passed_cases": sum(1 for item in results if item["passed"]),
        "elapsed_total_seconds": round(sum(elapsed_values), 6),
        "elapsed_median_seconds": round(statistics.median(elapsed_values), 6),
        "results": results,
    }


def result_map(evaluation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in evaluation["results"]}


def matrix_result(results: dict[str, dict[str, Any]], case_id: str) -> dict[str, Any]:
    return results.get(
        case_id,
        {
            "id": case_id,
            "expect": "invalid",
            "tags": [],
            "score": 0.0,
            "passed": False,
            "failures": [f"missing required matrix case: {case_id}"],
            "missing_expected_fragments": [f"missing required matrix case: {case_id}"],
            "elapsed_seconds": 0.0,
        },
    )


def ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 1.0
    return float(numerator) / float(denominator)


def average(values: list[float]) -> float:
    if not values:
        return 1.0
    return sum(values) / len(values)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]


def valid_quality_comparison(data: dict[str, Any]) -> bool:
    comparison = data.get("quality_comparison")
    if not isinstance(comparison, dict):
        return False
    return (
        reviewable_ref(comparison.get("baseline_result_ref"))
        and reviewable_ref(comparison.get("candidate_result_ref"))
        and comparison.get("baseline_result_ref") != comparison.get("candidate_result_ref")
        and isinstance(comparison.get("acceptance_criteria"), list)
        and bool(comparison.get("acceptance_criteria"))
        and all(isinstance(item, str) and len(item.strip()) >= 12 for item in comparison.get("acceptance_criteria") or [])
        and isinstance(comparison.get("outcome_quality_delta"), (int, float))
        and isinstance(comparison.get("overhead_ratio"), (int, float))
        and bool(comparison.get("recommendation"))
    )


def valid_observability_fields(data: dict[str, Any]) -> bool:
    return all(
        [
            isinstance(data.get("backend_provenance"), dict),
            isinstance(data.get("artifact_storage"), dict),
            isinstance(data.get("metrics"), dict),
            bool(data.get("evidence_ledger")),
            bool(data.get("source_of_truth_refs")),
            bool(data.get("verification_evidence")),
        ]
    )


def valid_handoff_context(data: dict[str, Any]) -> bool:
    return bool(data.get("source_of_truth_refs")) and bool(data.get("success_criteria")) and bool(data.get("verification_evidence"))


def rerun_consistency_rate(validator: Callable[[dict[str, Any]], list[str]], cases: list[dict[str, Any]]) -> float:
    consistent = 0
    for case in cases:
        first = validator(deepcopy(case["data"]))
        second = validator(deepcopy(case["data"]))
        if first == second:
            consistent += 1
    return ratio(consistent, len(cases))


def multi_metric_scorecard(
    evaluation: dict[str, Any],
    cases: list[dict[str, Any]],
    validator: Callable[[dict[str, Any]], list[str]],
    perf: dict[str, Any],
    max_large_ledger_seconds: float,
) -> dict[str, Any]:
    results = result_map(evaluation)
    valid_cases_only = [case for case in cases if case["expect"] == "valid"]
    invalid_cases_only = [case for case in cases if case["expect"] == "invalid"]
    critical_invalid_cases = [case for case in invalid_cases_only if "critical" in case_tags(case["id"])]
    missing_required_cases = sorted(case_id for case_id in REQUIRED_MATRIX_CASE_IDS if case_id not in results)

    valid_preservation_rate = ratio(
        sum(1 for case in valid_cases_only if matrix_result(results, case["id"])["passed"]),
        len(valid_cases_only),
    )
    invalid_detection_recall = ratio(
        sum(1 for case in invalid_cases_only if matrix_result(results, case["id"])["failures"]),
        len(invalid_cases_only),
    )
    expected_failure_match_rate = average(
        [float(matrix_result(results, case["id"])["score"]) for case in invalid_cases_only]
    )
    critical_miss_rate = ratio(
        sum(1 for case in critical_invalid_cases if not matrix_result(results, case["id"])["passed"]),
        len(critical_invalid_cases),
    )

    allowed_promotions = [
        case
        for case in cases
        if case["data"].get("final_recommendation") == "promote"
        and not matrix_result(results, case["id"])["failures"]
    ]
    promotion_precision = ratio(sum(1 for case in allowed_promotions if case["expect"] == "valid"), len(allowed_promotions))

    high_overhead_gate_score = float(matrix_result(results, "high-overhead-weak-promotion")["passed"])
    weak_positive_delta_gate_score = float(matrix_result(results, "weak-positive-delta-promotion")["passed"])
    acceptance_criteria_gate_score = float(matrix_result(results, "empty-acceptance-criteria")["passed"])
    final_recommendation_match_gate_score = float(matrix_result(results, "final-recommendation-mismatch")["passed"])
    quality_comparison_coverage = ratio(
        sum(1 for case in valid_cases_only if valid_quality_comparison(case["data"])),
        len(valid_cases_only),
    )
    outcome_quality_score = average(
        [
            quality_comparison_coverage,
            high_overhead_gate_score,
            weak_positive_delta_gate_score,
            acceptance_criteria_gate_score,
            final_recommendation_match_gate_score,
        ]
    )

    elapsed_values = [float(item["elapsed_seconds"]) for item in evaluation["results"]]
    p50 = percentile(elapsed_values, 0.50)
    p95 = percentile(elapsed_values, 0.95)
    is_baseline = evaluation["name"].startswith("legacy_")
    large_ledger_seconds = float(
        perf["baseline_elapsed_seconds"] if is_baseline else perf["candidate_elapsed_seconds"]
    )
    large_ledger_failures = perf["baseline_failures"] if is_baseline else perf["candidate_failures"]
    large_ledger_time_ratio = 1.0 if is_baseline else perf["candidate_to_baseline_time_ratio"]
    large_ledger_pass = (
        not large_ledger_failures
        and large_ledger_seconds <= max_large_ledger_seconds
    )
    threshold_denominator = max(max_large_ledger_seconds, 1e-12)
    large_ledger_budget_score = max(0.0, min(1.0, 1.0 - (large_ledger_seconds / threshold_denominator)))
    time_ratio_score = (
        1.0
        if large_ledger_time_ratio is None
        else min(1.0, 1.0 / max(1.0, float(large_ledger_time_ratio)))
    )
    efficiency_score = average([float(large_ledger_pass), large_ledger_budget_score, time_ratio_score])

    metrics_coverage = ratio(
        sum(
            1
            for case in valid_cases_only
            if isinstance(case["data"].get("metrics"), dict)
            and case["data"]["metrics"].get("worker_count") == len(case["data"].get("workers") or [])
            and "max_concurrency" in case["data"]["metrics"]
            and case["data"]["metrics"].get("write_scopes_disjoint") is True
        ),
        len(valid_cases_only),
    )
    parallelism_score = average(
        [
            metrics_coverage,
            float(matrix_result(results, "overlapping-write-scopes")["passed"]),
            float(matrix_result(results, "duplicate-worker-and-evidence")["passed"]),
        ]
    )

    consistency_rate = rerun_consistency_rate(validator, cases)
    reliability_score = average(
        [
            consistency_rate,
            float(matrix_result(results, "invalid-timestamp-and-extra-field")["passed"]),
            float(matrix_result(results, "missing-artifact-storage")["passed"]),
            float(matrix_result(results, "missing-metrics")["passed"]),
        ]
    )

    trace_completeness_rate = ratio(
        sum(1 for case in valid_cases_only if valid_observability_fields(case["data"])),
        len(valid_cases_only),
    )
    observability_score = average([trace_completeness_rate, expected_failure_match_rate])

    handoff_clarity_rate = ratio(
        sum(1 for case in valid_cases_only if valid_handoff_context(case["data"])),
        len(valid_cases_only),
    )
    human_dev_score = average([handoff_clarity_rate, expected_failure_match_rate])

    dimensions = {
        "promotion_decision_quality": {
            "score": round(average([valid_preservation_rate, invalid_detection_recall, expected_failure_match_rate, promotion_precision, 1 - critical_miss_rate]), 4),
            "metrics": {
                "critical_miss_rate": round(critical_miss_rate, 4),
                "invalid_detection_recall": round(invalid_detection_recall, 4),
                "valid_preservation_rate": round(valid_preservation_rate, 4),
                "expected_failure_match_rate": round(expected_failure_match_rate, 4),
                "promotion_precision": round(promotion_precision, 4),
            },
        },
        "outcome_quality": {
            "score": round(outcome_quality_score, 4),
            "metrics": {
                "quality_comparison_coverage": round(quality_comparison_coverage, 4),
                "high_overhead_gate_score": round(high_overhead_gate_score, 4),
                "weak_positive_delta_gate_score": round(weak_positive_delta_gate_score, 4),
                "acceptance_criteria_gate_score": round(acceptance_criteria_gate_score, 4),
                "final_recommendation_match_gate_score": round(final_recommendation_match_gate_score, 4),
            },
        },
        "efficiency_cost": {
            "score": round(efficiency_score, 4),
            "metrics": {
                "case_latency_p50_seconds": round(p50, 6),
                "case_latency_p95_seconds": round(p95, 6),
                "large_ledger_seconds": round(large_ledger_seconds, 6),
                "large_ledger_threshold_seconds": max_large_ledger_seconds,
                "large_ledger_budget_score": round(large_ledger_budget_score, 4),
                "large_ledger_time_ratio": large_ledger_time_ratio,
                "large_ledger_time_ratio_score": round(time_ratio_score, 4),
            },
        },
        "parallelism_efficiency": {
            "score": round(parallelism_score, 4),
            "metrics": {
                "worker_metrics_coverage": round(metrics_coverage, 4),
                "write_scope_conflict_detection": float(matrix_result(results, "overlapping-write-scopes")["passed"]),
                "duplicate_work_detection": float(matrix_result(results, "duplicate-worker-and-evidence")["passed"]),
            },
        },
        "reliability_reproducibility": {
            "score": round(reliability_score, 4),
            "metrics": {
                "rerun_consistency_rate": round(consistency_rate, 4),
                "schema_parity_detection": float(matrix_result(results, "invalid-timestamp-and-extra-field")["passed"]),
                "artifact_hygiene_detection": float(matrix_result(results, "missing-artifact-storage")["passed"]),
                "metrics_presence_detection": float(matrix_result(results, "missing-metrics")["passed"]),
            },
        },
        "observability_diagnosability": {
            "score": round(observability_score, 4),
            "metrics": {
                "trace_completeness_rate": round(trace_completeness_rate, 4),
                "root_cause_localization_rate": round(expected_failure_match_rate, 4),
            },
        },
        "human_developer_experience": {
            "score": round(human_dev_score, 4),
            "metrics": {
                "handoff_clarity_rate": round(handoff_clarity_rate, 4),
                "review_burden_reduction_proxy": round(expected_failure_match_rate, 4),
            },
        },
    }
    overall_score = sum(dimensions[name]["score"] * weight for name, weight in DIMENSION_WEIGHTS.items())
    dimension_gate_failures = [
        f"{name} below minimum {minimum:.2f}"
        for name, minimum in DIMENSION_MINIMUMS.items()
        if dimensions[name]["score"] < minimum
    ]
    hard_gate_failures = [
        failure
        for failure in [
            "critical_miss_rate > 0" if critical_miss_rate > 0 else "",
            "large_ledger_validation_failed" if not large_ledger_pass else "",
            *[f"missing required matrix case: {case_id}" for case_id in missing_required_cases],
            *dimension_gate_failures,
        ]
        if failure
    ]
    return {
        "overall_score": round(overall_score, 4),
        "weights": DIMENSION_WEIGHTS,
        "dimension_minimums": DIMENSION_MINIMUMS,
        "dimensions": dimensions,
        "hard_gate_failures": hard_gate_failures,
    }


def performance_comparison(worker_count: int, evidence_count: int, max_large_ledger_seconds: float) -> dict[str, Any]:
    data = large_run(worker_count, evidence_count)
    started = time.perf_counter()
    baseline_failures = baseline_lightweight_failures(deepcopy(data))
    baseline_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    candidate_failures = run_failures(deepcopy(data))
    candidate_elapsed = time.perf_counter() - started
    ratio = candidate_elapsed / baseline_elapsed if baseline_elapsed > 0 else None
    return {
        "worker_count": worker_count,
        "evidence_count": evidence_count,
        "baseline_elapsed_seconds": round(baseline_elapsed, 6),
        "candidate_elapsed_seconds": round(candidate_elapsed, 6),
        "candidate_to_baseline_time_ratio": round(ratio, 4) if ratio is not None else None,
        "baseline_failures": baseline_failures,
        "candidate_failures": candidate_failures,
        "max_large_ledger_seconds": max_large_ledger_seconds,
        "passed": not candidate_failures and candidate_elapsed <= max_large_ledger_seconds,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare legacy lightweight workflow validation with the hardened workflow-run validator.")
    parser.add_argument("--min-score-delta", type=float, default=MIN_SCORE_DELTA)
    parser.add_argument("--min-multi-metric-score", type=float, default=MIN_MULTI_METRIC_SCORE)
    parser.add_argument("--max-large-ledger-seconds", type=float, default=MAX_LARGE_LEDGER_SECONDS)
    parser.add_argument("--worker-count", type=int, default=1000)
    parser.add_argument("--evidence-count", type=int, default=2000)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = curated_cases()
    baseline = evaluate_validator("legacy_lightweight_workflow_validation", baseline_lightweight_failures, cases)
    candidate = evaluate_validator("hardened_workflow_run_validation", run_failures, cases)
    score_delta = round(candidate["average_score"] - baseline["average_score"], 4)
    perf = performance_comparison(args.worker_count, args.evidence_count, args.max_large_ledger_seconds)
    baseline_multi = multi_metric_scorecard(
        baseline,
        cases,
        baseline_lightweight_failures,
        perf,
        args.max_large_ledger_seconds,
    )
    candidate_multi = multi_metric_scorecard(
        candidate,
        cases,
        run_failures,
        perf,
        args.max_large_ledger_seconds,
    )
    multi_metric_delta = round(candidate_multi["overall_score"] - baseline_multi["overall_score"], 4)
    hard_gate_failures = candidate_multi["hard_gate_failures"]
    passed = (
        score_delta >= args.min_score_delta
        and candidate["average_score"] == 1.0
        and candidate_multi["overall_score"] >= args.min_multi_metric_score
        and not hard_gate_failures
        and perf["passed"]
    )
    payload = {
        "format": "sejong.workflow-run-comparison-benchmark/v0.1-draft",
        "passed": passed,
        "min_score_delta": args.min_score_delta,
        "min_multi_metric_score": args.min_multi_metric_score,
        "score_delta": score_delta,
        "multi_metric_delta": multi_metric_delta,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_multi_metric": baseline_multi,
        "candidate_multi_metric": candidate_multi,
        "performance": perf,
        "notes": [
            "Primary performance is defect-detection and valid-case preservation against the same use-case matrix.",
            "Promotion also requires the weighted multi-metric scorecard to pass quality, efficiency, parallelism, reliability, observability, and handoff gates.",
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "workflow_run_comparison "
            f"{'ok' if passed else 'failed'}: "
            f"baseline={baseline['average_score']} candidate={candidate['average_score']} "
            f"delta={score_delta} min_delta={args.min_score_delta} "
            f"multi={candidate_multi['overall_score']} min_multi={args.min_multi_metric_score} "
            f"candidate_time={perf['candidate_elapsed_seconds']}s baseline_time={perf['baseline_elapsed_seconds']}s"
        )
        if not passed:
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
