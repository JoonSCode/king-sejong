#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN_FORMAT = "sejong.product-evidence-plan/v0.1-draft"
RESULT_FORMAT = "sejong.product-evidence-result/v0.1-draft"
JUDGMENT_FORMAT = "sejong.product-evidence-judgment/v0.1-draft"
REQUIRED_CLASSES = {"analytics", "controlled_experiment", "user_research"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_failures(plan: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if plan.get("format") != PLAN_FORMAT:
        failures.append(f"unexpected plan format: {plan.get('format')}")
    for field in ("task_id", "claim_under_test", "success_claim_policy"):
        if not plan.get(field):
            failures.append(f"plan missing {field}")
    evidence_classes = set(plan.get("evidence_classes") or [])
    missing_classes = sorted(REQUIRED_CLASSES - evidence_classes)
    if missing_classes:
        failures.append("plan missing evidence classes: " + ", ".join(missing_classes))

    analytics = plan.get("analytics_requirements") or {}
    required_metrics = analytics.get("required_metrics") or []
    if not required_metrics:
        failures.append("analytics requirements need required_metrics")
    if not analytics.get("accepted_source_types"):
        failures.append("analytics requirements need accepted_source_types")

    experiment = plan.get("controlled_experiment") or {}
    if len(experiment.get("variants") or []) < 2:
        failures.append("controlled experiment requires at least two variants")
    for field in ("assignment_unit", "primary_metric_id", "minimum_sample_per_variant", "minimum_duration_days", "minimum_effect"):
        if experiment.get(field) in (None, "", []):
            failures.append(f"controlled experiment missing {field}")
    if not experiment.get("guardrail_metrics"):
        failures.append("controlled experiment requires guardrail_metrics")

    research = plan.get("user_research") or {}
    for field in ("segment", "minimum_participants", "required_outputs"):
        if research.get(field) in (None, "", []):
            failures.append(f"user research missing {field}")
    return failures


def analytics_failures(plan: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    analytics_plan = plan.get("analytics_requirements") or {}
    analytics = result.get("analytics") or {}
    source_type = analytics.get("source_type")
    if source_type not in (analytics_plan.get("accepted_source_types") or []):
        failures.append("analytics source_type is not accepted by the plan")
    metrics = analytics.get("metrics") or {}
    required_metric_ids = [item.get("metric_id") for item in analytics_plan.get("required_metrics") or []]
    for metric_id in required_metric_ids:
        if not metric_id:
            continue
        if metric_id not in metrics:
            failures.append(f"analytics missing required metric: {metric_id}")
            continue
        metric = metrics.get(metric_id) or {}
        if metric.get("baseline") is None or metric.get("candidate") is None:
            failures.append(f"analytics metric missing baseline or candidate value: {metric_id}")
    return failures


def experiment_failures(plan: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    experiment_plan = plan.get("controlled_experiment") or {}
    experiment = result.get("controlled_experiment") or {}
    variants = experiment.get("variants") or []
    if len(variants) < 2:
        failures.append("controlled experiment result requires at least two variants")
    minimum_sample = experiment_plan.get("minimum_sample_per_variant") or 0
    for variant in variants:
        if (variant.get("sample_size") or 0) < minimum_sample:
            failures.append(f"controlled experiment variant below sample threshold: {variant.get('id')}")
    if (experiment.get("duration_days") or 0) < (experiment_plan.get("minimum_duration_days") or 0):
        failures.append("controlled experiment duration is below plan threshold")
    if experiment.get("primary_metric_id") != experiment_plan.get("primary_metric_id"):
        failures.append("controlled experiment primary metric does not match plan")
    if (experiment.get("observed_effect") or 0) < (experiment_plan.get("minimum_effect") or 0):
        failures.append("controlled experiment effect is below plan threshold")
    if experiment.get("winner") != "candidate":
        failures.append("controlled experiment does not show candidate as winner")
    if experiment.get("guardrail_regressions"):
        failures.append("controlled experiment has guardrail regressions")
    return failures


def user_research_failures(plan: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    research_plan = plan.get("user_research") or {}
    research = result.get("user_research") or {}
    if (research.get("participants") or 0) < (research_plan.get("minimum_participants") or 0):
        failures.append("user research participants are below threshold")
    if not research.get("findings"):
        failures.append("user research findings are required")
    if "contradictions" not in research:
        failures.append("user research contradictions field is required")
    if research.get("segment") != research_plan.get("segment"):
        failures.append("user research segment does not match plan")
    return failures


def result_failures(plan: dict[str, Any], result: dict[str, Any]) -> tuple[list[str], dict[str, bool]]:
    failures: list[str] = []
    if result.get("format") != RESULT_FORMAT:
        failures.append(f"unexpected result format: {result.get('format')}")
    if result.get("task_id") != plan.get("task_id"):
        failures.append("result task_id does not match plan")
    if not result.get("external_evidence_refs"):
        failures.append("external evidence refs are required before claiming product success")

    class_failures = {
        "analytics": analytics_failures(plan, result),
        "controlled_experiment": experiment_failures(plan, result),
        "user_research": user_research_failures(plan, result),
    }
    failures.extend(failure for items in class_failures.values() for failure in items)
    class_passes = {name: not items for name, items in class_failures.items()}
    return failures, class_passes


def emit_judgment(payload: dict[str, Any], *, require_success: bool = False) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if require_success and not payload.get("can_claim_product_success"):
        return 1
    return 0 if payload.get("passed", False) else 1


def check_plan(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    failures = plan_failures(plan)
    passed = not failures
    payload = {
        "format": JUDGMENT_FORMAT,
        "generated_at": now_utc(),
        "task_id": plan.get("task_id", ""),
        "status": "ready_for_field_test" if passed else "invalid_plan",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "can_claim_product_success": False,
        "validated_evidence_classes": sorted(REQUIRED_CLASSES) if passed else [],
        "failures": failures,
        "notes": [
            "A valid field-validation plan only proves readiness to collect external evidence.",
            "Product success cannot be claimed until result evidence passes this gate.",
        ],
    }
    return emit_judgment(payload)


def judge_result(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    result = load_json(Path(args.result))
    failures = plan_failures(plan)
    class_passes: dict[str, bool] = {name: False for name in REQUIRED_CLASSES}
    if not failures:
        result_failure_list, class_passes = result_failures(plan, result)
        failures.extend(result_failure_list)
    passed_classes = sorted(name for name, passed in class_passes.items() if passed)
    score = round(len(passed_classes) / len(REQUIRED_CLASSES), 4)
    can_claim_success = not failures and score == 1.0
    payload = {
        "format": JUDGMENT_FORMAT,
        "generated_at": now_utc(),
        "task_id": plan.get("task_id", ""),
        "result_id": result.get("result_id", ""),
        "status": "success_supported" if can_claim_success else "insufficient_evidence",
        "passed": can_claim_success,
        "score": score,
        "can_claim_product_success": can_claim_success,
        "validated_evidence_classes": passed_classes,
        "failures": failures,
        "external_evidence_refs": result.get("external_evidence_refs") or [],
        "notes": [
            "This gate checks whether external evidence supports a product-success claim.",
            "It does not collect analytics itself; it validates evidence supplied by the user or runtime integrations.",
        ],
    }
    return emit_judgment(payload, require_success=args.require_success)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate external product evidence before Sejong claims product success.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("check-plan", help="Validate that a field validation plan is ready.")
    plan_parser.add_argument("--plan", required=True)
    plan_parser.set_defaults(func=check_plan)

    result_parser = subparsers.add_parser("judge-result", help="Judge external evidence against a field validation plan.")
    result_parser.add_argument("--plan", required=True)
    result_parser.add_argument("--result", required=True)
    result_parser.add_argument("--require-success", action="store_true")
    result_parser.set_defaults(func=judge_result)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
