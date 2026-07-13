from __future__ import annotations

from delegation_route_contract import (
    ROUTES,
    DelegationInput,
    fallback_reasons,
    hard_gate_failures,
    requires_worker_backend,
)


def route_scores(case: DelegationInput) -> dict[str, int]:
    scores = {route: 0 for route in ROUTES}
    if case.task_class in {"simple_lookup", "install_maintenance"}:
        scores["direct_execution"] += 3
    if case.evidence_breadth == "narrow":
        scores["direct_execution"] += 2
    if case.overhead_roi == "low":
        scores["direct_execution"] += 2
    if case.code_coupling in {"isolated", "bounded"}:
        scores["direct_execution"] += 1
    if case.write_risk in {"none", "low"}:
        scores["direct_execution"] += 1

    if case.task_class in {
        "implementation",
        "refactor_cleanup",
        "validation_review",
        "bundle_execution",
    }:
        scores["bounded_subagents"] += 2
    if case.evidence_breadth in {"moderate", "broad"}:
        scores["bounded_subagents"] += 2
    if case.code_coupling in {"isolated", "bounded"}:
        scores["bounded_subagents"] += 2
    if case.overhead_roi in {"medium", "high"}:
        scores["bounded_subagents"] += 2
    if case.write_risk in {"low", "medium"}:
        scores["bounded_subagents"] += 1

    if case.evidence_breadth == "broad":
        scores["team_executor"] += 2
    if case.overhead_roi == "high":
        scores["team_executor"] += 2
    if case.worker_scope_state == "disjoint":
        scores["team_executor"] += 3
    if case.worker_scope_state == "disjoint" and case.overhead_roi == "high":
        scores["team_executor"] += 1
    if case.task_class in {
        "implementation",
        "refactor_cleanup",
        "bundle_execution",
        "validation_review",
    }:
        scores["team_executor"] += 1
    if case.write_risk in {"medium", "high"}:
        scores["team_executor"] += 1

    if case.task_class in {"research", "architecture", "product_strategy"}:
        scores["research_fanout"] += 3
    if case.evidence_breadth in {"broad", "unknown"}:
        scores["research_fanout"] += 2
    if case.write_risk in {"none", "low"}:
        scores["research_fanout"] += 1
    if case.code_coupling in {"cross_module", "system_wide", "unknown"}:
        scores["research_fanout"] += 1
    if case.overhead_roi in {"medium", "high"}:
        scores["research_fanout"] += 1

    if case.seungjeongwon_guardrail_state == "weak":
        scores["no_write_dry_run"] += 4
    if case.code_coupling in {"system_wide", "unknown"} and case.write_risk in {
        "high",
        "unsafe",
    }:
        scores["no_write_dry_run"] += 4
    if (
        case.worker_scope_state in {"overlapping", "unknown"}
        and case.overhead_roi == "high"
    ):
        scores["no_write_dry_run"] += 2
    if case.uigwe_contract_state in {"required_missing", "unstable"}:
        scores["no_write_dry_run"] += 4
    return scores


def adjusted_scores(case: DelegationInput) -> dict[str, int]:
    scores = route_scores(case)
    if case.worker_scope_state in {"overlapping", "unknown"}:
        scores["team_executor"] = -1
    if case.worker_scope_state == "overlapping":
        scores["bounded_subagents"] = min(scores["bounded_subagents"], 1)
    if case.overhead_roi == "low":
        scores["team_executor"] = min(scores["team_executor"], 0)
        scores["bounded_subagents"] = min(scores["bounded_subagents"], 2)
        scores["research_fanout"] = min(scores["research_fanout"], 2)
    if case.evidence_breadth == "narrow" and case.task_class not in {
        "research",
        "architecture",
    }:
        scores["research_fanout"] = min(scores["research_fanout"], 1)

    reasons = fallback_reasons(case)
    requires_backend = requires_worker_backend(case)
    if requires_backend and reasons:
        scores["direct_execution"] = -1
        scores["bounded_subagents"] = -1
        scores["research_fanout"] = -1
        scores["team_executor"] = max(scores["team_executor"], scores["no_write_dry_run"] + 1)
    elif requires_backend:
        scores["direct_execution"] = -1
        scores["team_executor"] = -1
        native_route = max(
            ("bounded_subagents", "research_fanout"),
            key=lambda route: scores[route],
        )
        scores[native_route] = max(scores[native_route], scores["no_write_dry_run"] + 1)
    elif reasons:
        scores["bounded_subagents"] = -1
        scores["research_fanout"] = -1
    elif case.host_native_state == "available":
        scores["team_executor"] = -1
    return scores


def select_route(case: DelegationInput) -> str:
    if hard_gate_failures(case):
        return "no_write_dry_run"
    tie_break = {
        "no_write_dry_run": 5,
        "direct_execution": 4,
        "bounded_subagents": 3,
        "research_fanout": 2,
        "team_executor": 1,
    }
    scores = adjusted_scores(case)
    return max(ROUTES, key=lambda route: (scores[route], tie_break[route]))
