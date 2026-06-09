#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


FORMAT = "sejong.task-class-delegation-gate/v0.1-draft"

TASK_CLASSES = {
    "simple_lookup",
    "install_maintenance",
    "implementation",
    "refactor_cleanup",
    "validation_review",
    "research",
    "architecture",
    "product_strategy",
    "bundle_execution",
}
WRITE_RISKS = {"none", "low", "medium", "high", "unsafe"}
EVIDENCE_BREADTHS = {"narrow", "moderate", "broad", "unknown"}
CODE_COUPLINGS = {"isolated", "bounded", "cross_module", "system_wide", "unknown"}
OVERHEAD_ROIS = {"low", "medium", "high"}
UIGWE_STATES = {"none", "active", "handoff_ready", "required_missing", "unstable"}
SEUNGJEONGWON_GUARDRAIL_STATES = {"clear", "weak", "blocked"}
ARTIFACT_POLICIES = {"sejong_home_or_promoted_refs", "repo_runtime_artifacts", "unknown"}
WORKER_AUTHORITY_POLICIES = {"evidence_only", "consensus_approval", "final_verification"}
COURT_MODE_POLICIES = {"existing_surfaces_only", "creates_new_court_mode"}
WORKER_SCOPE_STATES = {"none", "disjoint", "overlapping", "unknown"}
WRITE_MODES = {"allowed", "no_write", "dry_run", "destructive"}

ROUTES = (
    "direct_execution",
    "bounded_subagents",
    "team_executor",
    "research_fanout",
    "no_write_dry_run",
)

FORBIDDEN_CLAIMS = [
    "Uigwe gate approval",
    "final synthesis",
    "final verification by workers",
    "majority-vote authority",
    "consensus approval",
    "scope widening",
]


@dataclass(frozen=True)
class DelegationInput:
    task_class: str
    write_risk: str = "low"
    evidence_breadth: str = "narrow"
    code_coupling: str = "isolated"
    overhead_roi: str = "low"
    uigwe_contract_state: str = "none"
    seungjeongwon_guardrail_state: str = "clear"
    artifact_policy: str = "sejong_home_or_promoted_refs"
    worker_authority_policy: str = "evidence_only"
    court_mode_policy: str = "existing_surfaces_only"
    worker_scope_state: str = "none"
    write_mode: str = "allowed"


def _validate_choice(name: str, value: str, choices: set[str]) -> None:
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {allowed}")


def validate_input(case: DelegationInput) -> None:
    _validate_choice("task_class", case.task_class, TASK_CLASSES)
    _validate_choice("write_risk", case.write_risk, WRITE_RISKS)
    _validate_choice("evidence_breadth", case.evidence_breadth, EVIDENCE_BREADTHS)
    _validate_choice("code_coupling", case.code_coupling, CODE_COUPLINGS)
    _validate_choice("overhead_roi", case.overhead_roi, OVERHEAD_ROIS)
    _validate_choice("uigwe_contract_state", case.uigwe_contract_state, UIGWE_STATES)
    _validate_choice(
        "seungjeongwon_guardrail_state",
        case.seungjeongwon_guardrail_state,
        SEUNGJEONGWON_GUARDRAIL_STATES,
    )
    _validate_choice("artifact_policy", case.artifact_policy, ARTIFACT_POLICIES)
    _validate_choice("worker_authority_policy", case.worker_authority_policy, WORKER_AUTHORITY_POLICIES)
    _validate_choice("court_mode_policy", case.court_mode_policy, COURT_MODE_POLICIES)
    _validate_choice("worker_scope_state", case.worker_scope_state, WORKER_SCOPE_STATES)
    _validate_choice("write_mode", case.write_mode, WRITE_MODES)


def hard_gates(case: DelegationInput) -> dict[str, bool]:
    return {
        "preserves_uigwe_contract": case.uigwe_contract_state != "unstable",
        "keeps_worker_outputs_evidence_only": case.worker_authority_policy == "evidence_only",
        "records_reviewable_evidence": True,
        "keeps_artifacts_under_sejong_home_or_promoted_refs": (
            case.artifact_policy == "sejong_home_or_promoted_refs"
        ),
        "does_not_create_new_court_mode": case.court_mode_policy == "existing_surfaces_only",
    }


def hard_gate_failures(case: DelegationInput) -> list[str]:
    failures = [name for name, passed in hard_gates(case).items() if not passed]
    if case.seungjeongwon_guardrail_state == "blocked":
        failures.append("seungjeongwon_guardrails_blocked")
    if case.uigwe_contract_state == "required_missing":
        failures.append("uigwe_contract_required_before_writes")
    if case.write_mode in {"no_write", "dry_run", "destructive"}:
        failures.append(f"write_mode_{case.write_mode}")
    if case.write_risk == "unsafe":
        failures.append("unsafe_write_risk")
    return failures


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

    if case.task_class in {"implementation", "refactor_cleanup", "validation_review", "bundle_execution"}:
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
    if case.task_class in {"implementation", "refactor_cleanup", "bundle_execution", "validation_review"}:
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
    if case.code_coupling in {"system_wide", "unknown"} and case.write_risk in {"high", "unsafe"}:
        scores["no_write_dry_run"] += 4
    if case.worker_scope_state in {"overlapping", "unknown"} and case.overhead_roi == "high":
        scores["no_write_dry_run"] += 2
    if case.uigwe_contract_state in {"required_missing", "unstable"}:
        scores["no_write_dry_run"] += 4
    return scores


def route_tie_breaker(route: str) -> int:
    order = {
        "no_write_dry_run": 5,
        "direct_execution": 4,
        "bounded_subagents": 3,
        "research_fanout": 2,
        "team_executor": 1,
    }
    return order[route]


def select_route(case: DelegationInput) -> str:
    if hard_gate_failures(case):
        return "no_write_dry_run"
    scores = route_scores(case)
    if case.worker_scope_state in {"overlapping", "unknown"}:
        scores["team_executor"] = -1
    if case.worker_scope_state == "overlapping":
        scores["bounded_subagents"] = min(scores["bounded_subagents"], 1)
    if case.overhead_roi == "low":
        scores["team_executor"] = min(scores["team_executor"], 0)
        scores["bounded_subagents"] = min(scores["bounded_subagents"], 2)
        scores["research_fanout"] = min(scores["research_fanout"], 2)
    if case.evidence_breadth == "narrow" and case.task_class not in {"research", "architecture"}:
        scores["research_fanout"] = min(scores["research_fanout"], 1)
    return max(ROUTES, key=lambda route: (scores[route], route_tie_breaker(route)))


def required_evidence(route: str, case: DelegationInput) -> list[str]:
    evidence = ["fresh verification evidence", "reviewable evidence refs"]
    if route in {"bounded_subagents", "team_executor"}:
        evidence.extend(["bounded worker scope", "worker output treated as evidence only"])
    if route == "team_executor":
        evidence.extend(["disjoint file leases or equivalent scope proof", "durable mailbox or workflow-run evidence"])
    if route == "research_fanout":
        evidence.extend(["known/inferred/unknown separation", "source refs for blocking facts"])
    if route == "no_write_dry_run":
        evidence.extend(["blocker reason", "recommended Uigwe or Seungjeongwon re-entry target"])
    if case.uigwe_contract_state in {"active", "handoff_ready"}:
        evidence.append("Uigwe contract refs preserved")
    return evidence


def allowed_outputs(route: str) -> list[str]:
    if route == "direct_execution":
        return ["implementation notes", "verification observations", "bounded evidence"]
    if route == "bounded_subagents":
        return ["bounded worker briefs", "evidence refs", "risks", "blockers"]
    if route == "team_executor":
        return ["leased implementation slices", "mailbox evidence", "verification observations", "blockers"]
    if route == "research_fanout":
        return ["known/inferred/unknown brief", "source refs", "decision-enabling evidence"]
    return ["dry-run findings", "blocker evidence", "re-entry recommendation"]


def reentry_target(route: str, case: DelegationInput) -> str:
    if case.uigwe_contract_state in {"required_missing", "unstable"}:
        return "uigwe"
    if case.seungjeongwon_guardrail_state in {"weak", "blocked"}:
        return "seungjeongwon"
    if route == "research_fanout":
        return "jangyeongsil"
    return "none"


def confidence(route: str, case: DelegationInput, failures: list[str]) -> float:
    if failures:
        return 0.99
    scores = route_scores(case)
    ordered = sorted(scores.values(), reverse=True)
    margin = ordered[0] - ordered[1] if len(ordered) > 1 else ordered[0]
    base = 0.76 + min(margin, 4) * 0.04
    if route == "team_executor" and case.worker_scope_state != "disjoint":
        base -= 0.2
    if case.evidence_breadth == "unknown":
        base -= 0.08
    return round(max(0.5, min(0.98, base)), 2)


def evaluate(case: DelegationInput) -> dict[str, Any]:
    validate_input(case)
    failures = hard_gate_failures(case)
    selected = select_route(case)
    scores = route_scores(case)
    return {
        "format": FORMAT,
        "selected_route": selected,
        "confidence": confidence(selected, case, failures),
        "hard_gates": hard_gates(case),
        "hard_gate_failures": failures,
        "route_scores": scores,
        "decision_factors": asdict(case),
        "required_evidence": required_evidence(selected, case),
        "allowed_outputs": allowed_outputs(selected),
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "recommended_reentry_target": reentry_target(selected, case),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select a King Sejong execution/delegation route for a task class.")
    parser.add_argument("--from-json", help="Read decision factors from a JSON file, or '-' for stdin.")
    parser.add_argument("--task-class", choices=sorted(TASK_CLASSES))
    parser.add_argument("--write-risk", choices=sorted(WRITE_RISKS), default="low")
    parser.add_argument("--evidence-breadth", choices=sorted(EVIDENCE_BREADTHS), default="narrow")
    parser.add_argument("--code-coupling", choices=sorted(CODE_COUPLINGS), default="isolated")
    parser.add_argument("--overhead-roi", choices=sorted(OVERHEAD_ROIS), default="low")
    parser.add_argument("--uigwe-contract-state", choices=sorted(UIGWE_STATES), default="none")
    parser.add_argument("--seungjeongwon-guardrail-state", choices=sorted(SEUNGJEONGWON_GUARDRAIL_STATES), default="clear")
    parser.add_argument("--artifact-policy", choices=sorted(ARTIFACT_POLICIES), default="sejong_home_or_promoted_refs")
    parser.add_argument("--worker-authority-policy", choices=sorted(WORKER_AUTHORITY_POLICIES), default="evidence_only")
    parser.add_argument("--court-mode-policy", choices=sorted(COURT_MODE_POLICIES), default="existing_surfaces_only")
    parser.add_argument("--worker-scope-state", choices=sorted(WORKER_SCOPE_STATES), default="none")
    parser.add_argument("--write-mode", choices=sorted(WRITE_MODES), default="allowed")
    return parser.parse_args(argv)


def input_from_args(args: argparse.Namespace) -> DelegationInput:
    if args.from_json:
        raw = sys.stdin.read() if args.from_json == "-" else Path(args.from_json).read_text(encoding="utf-8")
        payload = json.loads(raw)
        return DelegationInput(**payload)
    if not args.task_class:
        raise ValueError("--task-class is required unless --from-json is used")
    return DelegationInput(
        task_class=args.task_class,
        write_risk=args.write_risk,
        evidence_breadth=args.evidence_breadth,
        code_coupling=args.code_coupling,
        overhead_roi=args.overhead_roi,
        uigwe_contract_state=args.uigwe_contract_state,
        seungjeongwon_guardrail_state=args.seungjeongwon_guardrail_state,
        artifact_policy=args.artifact_policy,
        worker_authority_policy=args.worker_authority_policy,
        court_mode_policy=args.court_mode_policy,
        worker_scope_state=args.worker_scope_state,
        write_mode=args.write_mode,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        case = input_from_args(parse_args(argv))
        print(json.dumps(evaluate(case), indent=2, sort_keys=True))
        return 0
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
