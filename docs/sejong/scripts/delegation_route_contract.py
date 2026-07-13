from __future__ import annotations

from dataclasses import dataclass
from typing import Final


FORMAT: Final = "sejong.task-class-delegation-gate/v0.1-draft"
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
ARTIFACT_POLICIES = {
    "sejong_home_or_promoted_refs",
    "repo_runtime_artifacts",
    "unknown",
}
WORKER_AUTHORITY_POLICIES = {
    "evidence_only",
    "consensus_approval",
    "final_verification",
}
COURT_MODE_POLICIES = {"existing_surfaces_only", "creates_new_court_mode"}
WORKER_SCOPE_STATES = {"none", "disjoint", "overlapping", "unknown"}
WRITE_MODES = {"allowed", "no_write", "dry_run", "destructive"}
HOST_NATIVE_STATES = {"unknown", "available", "unavailable"}
NATIVE_MESSAGING_STATES = {"unknown", "available", "unavailable"}
NATIVE_WRITE_ISOLATIONS = {"unknown", "shared_workspace", "worktree"}
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


@dataclass(frozen=True, slots=True)
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
    host_native_state: str = "unknown"
    host_native_direct_messaging: str = "unknown"
    host_native_write_isolation: str = "unknown"
    requires_independent_process: bool = False
    requires_cross_session_recovery: bool = False
    requires_write_isolation: bool = False
    requires_peer_messaging: bool = False


def _validate_choice(name: str, value: str, choices: set[str]) -> None:
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(choices))}")


def validate_input(case: DelegationInput) -> None:
    fields = (
        ("task_class", case.task_class, TASK_CLASSES),
        ("write_risk", case.write_risk, WRITE_RISKS),
        ("evidence_breadth", case.evidence_breadth, EVIDENCE_BREADTHS),
        ("code_coupling", case.code_coupling, CODE_COUPLINGS),
        ("overhead_roi", case.overhead_roi, OVERHEAD_ROIS),
        ("uigwe_contract_state", case.uigwe_contract_state, UIGWE_STATES),
        (
            "seungjeongwon_guardrail_state",
            case.seungjeongwon_guardrail_state,
            SEUNGJEONGWON_GUARDRAIL_STATES,
        ),
        ("artifact_policy", case.artifact_policy, ARTIFACT_POLICIES),
        (
            "worker_authority_policy",
            case.worker_authority_policy,
            WORKER_AUTHORITY_POLICIES,
        ),
        ("court_mode_policy", case.court_mode_policy, COURT_MODE_POLICIES),
        ("worker_scope_state", case.worker_scope_state, WORKER_SCOPE_STATES),
        ("write_mode", case.write_mode, WRITE_MODES),
        ("host_native_state", case.host_native_state, HOST_NATIVE_STATES),
        (
            "host_native_direct_messaging",
            case.host_native_direct_messaging,
            NATIVE_MESSAGING_STATES,
        ),
        (
            "host_native_write_isolation",
            case.host_native_write_isolation,
            NATIVE_WRITE_ISOLATIONS,
        ),
    )
    for name, value, choices in fields:
        _validate_choice(name, value, choices)
    boolean_fields = (
        "requires_independent_process",
        "requires_cross_session_recovery",
        "requires_write_isolation",
        "requires_peer_messaging",
    )
    for name in boolean_fields:
        if type(getattr(case, name)) is not bool:
            raise ValueError(f"{name} must be a boolean")


def hard_gates(case: DelegationInput) -> dict[str, bool]:
    return {
        "preserves_uigwe_contract": case.uigwe_contract_state != "unstable",
        "keeps_worker_outputs_evidence_only": case.worker_authority_policy
        == "evidence_only",
        "records_reviewable_evidence": True,
        "keeps_artifacts_under_sejong_home_or_promoted_refs": case.artifact_policy
        == "sejong_home_or_promoted_refs",
        "does_not_create_new_court_mode": case.court_mode_policy
        == "existing_surfaces_only",
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
    if (
        case.worker_scope_state in {"overlapping", "unknown"}
        and requires_worker_backend(case)
    ):
        failures.append("worker_scope_unsafe")
    return failures


def requires_worker_backend(case: DelegationInput) -> bool:
    return any((
        case.requires_independent_process,
        case.requires_cross_session_recovery,
        case.requires_write_isolation,
        case.requires_peer_messaging,
    ))


def fallback_reasons(case: DelegationInput) -> list[str]:
    reasons: list[str] = []
    if case.host_native_state == "unavailable":
        reasons.append("host_native_unavailable")
    if case.requires_independent_process:
        reasons.append("independent_process_required")
    if case.requires_cross_session_recovery:
        reasons.append("cross_session_recovery_required")
    if case.requires_write_isolation and case.host_native_write_isolation != "worktree":
        reasons.append("native_write_isolation_unavailable")
    if (
        case.requires_peer_messaging
        and case.host_native_direct_messaging != "available"
    ):
        reasons.append("native_peer_messaging_unavailable")
    return reasons
