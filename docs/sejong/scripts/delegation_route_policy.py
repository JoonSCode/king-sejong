from __future__ import annotations

from dataclasses import asdict

from delegation_route_contract import (
    FORBIDDEN_CLAIMS,
    FORMAT,
    DelegationInput,
    fallback_reasons,
    hard_gate_failures,
    hard_gates,
    requires_worker_backend,
    validate_input,
)
from delegation_route_scoring import adjusted_scores, select_route
from team_executor_runtime import HEALTHY


def selected_backend(route: str) -> str:
    return {
        "direct_execution": "current_session",
        "bounded_subagents": "codex_native",
        "team_executor": "team_executor",
        "research_fanout": "codex_native",
        "no_write_dry_run": "none",
    }[route]


def required_evidence(route: str, backend: str, case: DelegationInput) -> list[str]:
    evidence = ["fresh verification evidence", "reviewable evidence refs"]
    if route in {"bounded_subagents", "team_executor"}:
        evidence += ["bounded worker scope", "worker output treated as evidence only"]
    if backend == "codex_native":
        evidence += ["native agent thread refs", "terminal delegation receipts"]
    if backend == "team_executor":
        evidence += [
            "healthy TeamExecutor preflight receipt",
            "disjoint file leases or equivalent scope proof",
            "durable mailbox or workflow-run evidence",
        ]
    if route == "research_fanout":
        evidence += [
            "known/inferred/unknown separation",
            "source refs for blocking facts",
        ]
    if route == "no_write_dry_run":
        evidence += [
            "blocker reason",
            "recommended Uigwe or Seungjeongwon re-entry target",
        ]
    if case.uigwe_contract_state in {"active", "handoff_ready"}:
        evidence.append("Uigwe contract refs preserved")
    return evidence


def _reentry_target(route: str, case: DelegationInput) -> str:
    if case.uigwe_contract_state in {"required_missing", "unstable"}:
        return "uigwe"
    if case.seungjeongwon_guardrail_state in {"weak", "blocked"}:
        return "seungjeongwon"
    if (
        route == "no_write_dry_run"
        and requires_worker_backend(case)
        and case.team_executor_health != HEALTHY
    ):
        return "seungjeongwon"
    return "jangyeongsil" if route == "research_fanout" else "none"


def _allowed_outputs(route: str) -> list[str]:
    return {
        "direct_execution": [
            "implementation notes",
            "verification observations",
            "bounded evidence",
        ],
        "bounded_subagents": [
            "bounded worker briefs",
            "evidence refs",
            "risks",
            "blockers",
        ],
        "team_executor": [
            "leased implementation slices",
            "mailbox evidence",
            "verification observations",
            "blockers",
        ],
        "research_fanout": [
            "known/inferred/unknown brief",
            "source refs",
            "decision-enabling evidence",
        ],
        "no_write_dry_run": [
            "dry-run findings",
            "blocker evidence",
            "re-entry recommendation",
        ],
    }[route]


def evaluate(case: DelegationInput) -> dict[str, object]:
    validate_input(case)
    failures = hard_gate_failures(case)
    route = select_route(case)
    backend = selected_backend(route)
    scores = adjusted_scores(case)
    ordered = sorted(scores.values(), reverse=True)
    confidence = (
        0.99
        if failures
        else round(
            max(0.5, min(0.98, 0.76 + min(ordered[0] - ordered[1], 4) * 0.04)),
            2,
        )
    )
    capability_notes: list[str] = []
    if case.host_native_state == "unknown":
        capability_notes.append("host_native_capability_unknown")
    if case.team_executor_health != HEALTHY:
        capability_notes.append(f"team_executor_health_{case.team_executor_health}")
    return {
        "format": FORMAT,
        "selected_route": route,
        "selected_backend": backend,
        "fallback_reasons": fallback_reasons(case),
        "backend_health": {"team_executor": case.team_executor_health},
        "capability_notes": capability_notes,
        "confidence": confidence,
        "hard_gates": hard_gates(case),
        "hard_gate_failures": failures,
        "route_scores": scores,
        "decision_factors": asdict(case),
        "required_evidence": required_evidence(route, backend, case),
        "allowed_outputs": _allowed_outputs(route),
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "recommended_reentry_target": _reentry_target(route, case),
    }
