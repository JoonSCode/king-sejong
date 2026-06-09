#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
FORMAT = "sejong.orchestrator-hypothesis-matrix/v0.1-draft"
MIN_HYPOTHESES_PER_AREA = 10
MIN_OVERALL_SCORE = 0.86

DIMENSION_WEIGHTS = {
    "outcome_quality": 0.24,
    "guardrail_integrity": 0.20,
    "observability_diagnosability": 0.16,
    "reliability_reproducibility": 0.14,
    "efficiency_cost": 0.10,
    "parallelism_fit": 0.08,
    "human_developer_experience": 0.08,
}

DIMENSION_MINIMUMS = {
    "outcome_quality": 0.80,
    "guardrail_integrity": 1.00,
    "observability_diagnosability": 0.85,
    "reliability_reproducibility": 0.85,
    "efficiency_cost": 0.55,
    "parallelism_fit": 0.50,
    "human_developer_experience": 0.70,
}

HARD_GATES = {
    "preserves_uigwe_contract",
    "keeps_worker_outputs_evidence_only",
    "records_reviewable_evidence",
    "keeps_artifacts_under_sejong_home_or_promoted_refs",
    "does_not_create_new_court_mode",
}

REQUIRED_AREA_IDS = {
    "hypothesis_selection_gate",
    "orchestrator_backend_policy",
    "architecture_refactor_policy",
}

TIE_BREAKER_DIMENSIONS = [
    "guardrail_integrity",
    "observability_diagnosability",
    "reliability_reproducibility",
    "outcome_quality",
    "efficiency_cost",
    "human_developer_experience",
    "parallelism_fit",
]


@dataclass(frozen=True)
class Candidate:
    area_id: str
    id: str
    hypothesis: str
    implementation: str
    measurement: dict[str, Any]
    metrics: dict[str, float]
    evidence_refs: list[str]
    implementation_refs: list[str]
    verification_refs: list[str]
    hard_gates: dict[str, bool]


@dataclass(frozen=True)
class TrialCase:
    area_id: str
    id: str
    dimension: str
    requires: tuple[str, ...]
    forbids: tuple[str, ...] = ()
    weight: float = 1.0


@dataclass(frozen=True)
class OperationalCorpusCase:
    area_id: str
    id: str
    expected_candidate_id: str
    evidence_refs: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    rationale: str


OPERATIONAL_CORPUS = [
    OperationalCorpusCase(
        "hypothesis_selection_gate",
        "instruction-taskset-and-scorecard-gate",
        "ranked-matrix-with-tie-breakers",
        (
            "docs/sejong/examples/validation/uigwe-instruction-surface-task-set.json",
            "docs/sejong/examples/validation/runs/uigwe-instruction-surface.scorecard.json",
            "docs/sejong/scripts/benchmark_instruction_surface.py",
        ),
        ("candidate_coverage", "reviewable_evidence", "deterministic_replay", "tie_breakers"),
        "Instruction-surface promotion already depends on frozen scenarios, generated scorecards, and deterministic replay.",
    ),
    OperationalCorpusCase(
        "hypothesis_selection_gate",
        "sejong-seed-taskset-route-evidence",
        "ranked-matrix-with-tie-breakers",
        (
            "docs/sejong/examples/validation/sejong-seed-task-set.json",
            "docs/sejong/scripts/benchmark_sejong_surface.py",
        ),
        ("multi_candidate", "same_acceptance_criteria", "adoption_output"),
        "Sejong route quality is validated by a scenario set rather than a one-off candidate answer.",
    ),
    OperationalCorpusCase(
        "orchestrator_backend_policy",
        "promoted-workflow-run-corpus",
        "lead-owned-bounded-subagents",
        (
            "docs/sejong/examples/workflow-run-corpus/deep-research-codex-subagents/workflow-run.json",
            "docs/sejong/examples/workflow-run-corpus/team-executor/workflow-run.json",
            "docs/sejong/examples/workflow-run-corpus/host-native-team/workflow-run.json",
            "docs/sejong/scripts/audit_workflow_run_risks.py",
        ),
        ("lead_synthesis", "worker_evidence_only", "bounded_parallelism", "backend_provenance"),
        "Promoted workflow-run evidence keeps worker output subordinate while comparing backend value and risk.",
    ),
    OperationalCorpusCase(
        "orchestrator_backend_policy",
        "workflow-comparison-and-stability-gates",
        "lead-owned-bounded-subagents",
        (
            "docs/sejong/scripts/benchmark_workflow_run_comparison.py",
            "docs/sejong/scripts/benchmark_workflow_run_stability.py",
            "docs/sejong/examples/workflow-run-corpus/evidence/candidate-hardened-workflow-run.md",
        ),
        ("quality_delta_measurement", "overhead_budget", "fallback_path", "disjoint_writes"),
        "Backend policy must be justified by quality delta, overhead, stability, and write-scope evidence.",
    ),
    OperationalCorpusCase(
        "architecture_refactor_policy",
        "workflow-run-gate-without-new-court-mode",
        "thin-validation-layer",
        (
            "docs/sejong/WORKFLOW_RUN.md",
            "docs/sejong/workflow-run.schema.json",
            "docs/sejong/examples/workflow-run-corpus/README.md",
        ),
        ("preserves_architecture", "no_new_court_mode", "preserves_workflow_run", "no_new_runtime"),
        "The existing workflow-run gate is already promoted without adding a new Sejong court mode.",
    ),
    OperationalCorpusCase(
        "architecture_refactor_policy",
        "outcome-evaluation-composition",
        "thin-validation-layer",
        (
            "docs/sejong/examples/outcome-evaluation/tagback-growth/comparison.result.json",
            "docs/sejong/examples/outcome-evaluation/sejong-long-session/task.json",
            "docs/sejong/scripts/sejong_integrated_quality_gate.py",
        ),
        ("fills_measurement_gap", "instruction_guard", "unit_tests", "docs_clear"),
        "Outcome and integrated quality gates show measurement can be added as a layer over existing court-mode boundaries.",
    ),
]


TRIAL_CASES = [
    TrialCase("hypothesis_selection_gate", "covers-ten-candidates", "outcome_quality", ("candidate_coverage", "multi_candidate")),
    TrialCase("hypothesis_selection_gate", "selects-adoptable-output", "outcome_quality", ("adoption_output", "same_acceptance_criteria")),
    TrialCase("hypothesis_selection_gate", "preserves-authority-gates", "guardrail_integrity", ("authority_gates",), ("worker_majority_authority",)),
    TrialCase("hypothesis_selection_gate", "keeps-workflow-run-separate", "guardrail_integrity", ("workflow_run_separate",)),
    TrialCase("hypothesis_selection_gate", "records-reviewable-refs", "observability_diagnosability", ("reviewable_evidence", "implementation_refs")),
    TrialCase("hypothesis_selection_gate", "records-rejections", "observability_diagnosability", ("rejected_alternatives",)),
    TrialCase("hypothesis_selection_gate", "replays-deterministically", "reliability_reproducibility", ("deterministic_replay",)),
    TrialCase("hypothesis_selection_gate", "separates-ties", "reliability_reproducibility", ("tie_breakers",)),
    TrialCase("hypothesis_selection_gate", "avoids-schema-churn", "efficiency_cost", ("low_schema_churn",)),
    TrialCase("hypothesis_selection_gate", "avoids-runtime-overhead", "efficiency_cost", ("low_runtime_overhead",)),
    TrialCase("hypothesis_selection_gate", "supports-independent-comparison", "parallelism_fit", ("parallel_safe",)),
    TrialCase("hypothesis_selection_gate", "covers-broad-hypothesis-space", "parallelism_fit", ("multi_candidate",)),
    TrialCase("hypothesis_selection_gate", "has-clear-cli", "human_developer_experience", ("clear_cli",)),
    TrialCase("hypothesis_selection_gate", "reduces-manual-burden", "human_developer_experience", ("low_manual_burden",)),
    TrialCase("orchestrator_backend_policy", "uses-independent-scopes", "outcome_quality", ("independent_scopes",)),
    TrialCase("orchestrator_backend_policy", "measures-quality-delta", "outcome_quality", ("quality_delta_measurement",)),
    TrialCase("orchestrator_backend_policy", "lead-owns-synthesis", "guardrail_integrity", ("lead_synthesis",)),
    TrialCase("orchestrator_backend_policy", "workers-stay-evidence", "guardrail_integrity", ("worker_evidence_only",), ("worker_majority_authority",)),
    TrialCase("orchestrator_backend_policy", "records-backend-provenance", "observability_diagnosability", ("backend_provenance",)),
    TrialCase("orchestrator_backend_policy", "records-verification-refs", "observability_diagnosability", ("verification_refs",)),
    TrialCase("orchestrator_backend_policy", "has-fallback-path", "reliability_reproducibility", ("fallback_path",)),
    TrialCase("orchestrator_backend_policy", "keeps-write-scopes-disjoint", "reliability_reproducibility", ("disjoint_writes",)),
    TrialCase("orchestrator_backend_policy", "keeps-overhead-budget", "efficiency_cost", ("overhead_budget",)),
    TrialCase("orchestrator_backend_policy", "avoids-unneeded-fanout", "efficiency_cost", ("selective_activation",)),
    TrialCase("orchestrator_backend_policy", "bounds-parallelism", "parallelism_fit", ("bounded_parallelism",)),
    TrialCase("orchestrator_backend_policy", "fits-concurrency-to-task", "parallelism_fit", ("concurrency_fit",)),
    TrialCase("orchestrator_backend_policy", "explains-delegation", "human_developer_experience", ("clear_when_to_delegate",)),
    TrialCase("orchestrator_backend_policy", "keeps-operator-burden-low", "human_developer_experience", ("low_operator_burden",)),
    TrialCase("architecture_refactor_policy", "fills-measurement-gap", "outcome_quality", ("fills_measurement_gap",)),
    TrialCase("architecture_refactor_policy", "preserves-existing-architecture", "outcome_quality", ("preserves_architecture",)),
    TrialCase("architecture_refactor_policy", "does-not-create-court-mode", "guardrail_integrity", ("no_new_court_mode",)),
    TrialCase("architecture_refactor_policy", "preserves-workflow-run-role", "guardrail_integrity", ("preserves_workflow_run",)),
    TrialCase("architecture_refactor_policy", "adds-instruction-guard", "observability_diagnosability", ("instruction_guard",)),
    TrialCase("architecture_refactor_policy", "adds-unit-tests", "observability_diagnosability", ("unit_tests",)),
    TrialCase("architecture_refactor_policy", "avoids-schema-migration", "reliability_reproducibility", ("no_schema_churn",)),
    TrialCase("architecture_refactor_policy", "replays-locally", "reliability_reproducibility", ("replayable",)),
    TrialCase("architecture_refactor_policy", "keeps-diff-small", "efficiency_cost", ("low_churn",)),
    TrialCase("architecture_refactor_policy", "avoids-new-runtime", "efficiency_cost", ("no_new_runtime",)),
    TrialCase("architecture_refactor_policy", "stays-worker-compatible", "parallelism_fit", ("compatible_with_workers",)),
    TrialCase("architecture_refactor_policy", "avoids-write-overlap", "parallelism_fit", ("no_write_overlap",)),
    TrialCase("architecture_refactor_policy", "keeps-mental-model-simple", "human_developer_experience", ("simple_mental_model",)),
    TrialCase("architecture_refactor_policy", "documents-usage", "human_developer_experience", ("docs_clear",)),
]


ALL_SELECTION_CAPS = {
    "candidate_coverage",
    "multi_candidate",
    "adoption_output",
    "same_acceptance_criteria",
    "authority_gates",
    "workflow_run_separate",
    "reviewable_evidence",
    "implementation_refs",
    "rejected_alternatives",
    "deterministic_replay",
    "tie_breakers",
    "low_schema_churn",
    "low_runtime_overhead",
    "parallel_safe",
    "clear_cli",
    "low_manual_burden",
}
ALL_BACKEND_CAPS = {
    "independent_scopes",
    "quality_delta_measurement",
    "lead_synthesis",
    "worker_evidence_only",
    "backend_provenance",
    "verification_refs",
    "fallback_path",
    "disjoint_writes",
    "overhead_budget",
    "selective_activation",
    "bounded_parallelism",
    "concurrency_fit",
    "clear_when_to_delegate",
    "low_operator_burden",
}
ALL_ARCHITECTURE_CAPS = {
    "fills_measurement_gap",
    "preserves_architecture",
    "no_new_court_mode",
    "preserves_workflow_run",
    "instruction_guard",
    "unit_tests",
    "no_schema_churn",
    "replayable",
    "low_churn",
    "no_new_runtime",
    "compatible_with_workers",
    "no_write_overlap",
    "simple_mental_model",
    "docs_clear",
}


CANDIDATE_CAPABILITIES = {
    "ranked-matrix-with-tie-breakers": ALL_SELECTION_CAPS,
    "elo-tournament-only": ALL_SELECTION_CAPS - {"reviewable_evidence", "implementation_refs", "low_runtime_overhead"},
    "llm-judge-only": ALL_SELECTION_CAPS - {"deterministic_replay", "tie_breakers", "reviewable_evidence", "low_runtime_overhead"},
    "static-checklist-only": ALL_SELECTION_CAPS - {"multi_candidate", "adoption_output", "tie_breakers", "parallel_safe"},
    "workflow-run-overload": ALL_SELECTION_CAPS - {"workflow_run_separate", "low_schema_churn", "low_runtime_overhead", "low_manual_burden"},
    "manual-sillok-ledger": ALL_SELECTION_CAPS - {"deterministic_replay", "clear_cli", "low_manual_burden", "parallel_safe"},
    "pairwise-baseline-candidate-only": ALL_SELECTION_CAPS - {"candidate_coverage", "multi_candidate", "parallel_safe"},
    "single-best-first": ALL_SELECTION_CAPS - {"candidate_coverage", "multi_candidate", "rejected_alternatives", "parallel_safe"},
    "scorecard-without-adoption-ledger": ALL_SELECTION_CAPS - {"adoption_output", "rejected_alternatives"},
    "randomized-ablation": ALL_SELECTION_CAPS - {"deterministic_replay", "tie_breakers", "reviewable_evidence", "low_manual_burden"},
    "lead-owned-bounded-subagents": ALL_BACKEND_CAPS,
    "deterministic-yaml-orchestrator": ALL_BACKEND_CAPS - {"fallback_path", "concurrency_fit", "low_operator_burden"},
    "host-native-team-when-supported": ALL_BACKEND_CAPS - {"fallback_path", "overhead_budget"},
    "team-executor-mailbox-default": ALL_BACKEND_CAPS - {"selective_activation", "overhead_budget", "low_operator_burden"},
    "manual-shadow-first": ALL_BACKEND_CAPS - {"quality_delta_measurement", "verification_refs", "concurrency_fit"},
    "codex-mock-workflow": ALL_BACKEND_CAPS - {"independent_scopes", "clear_when_to_delegate"},
    "single-agent-with-escalation": ALL_BACKEND_CAPS - {"bounded_parallelism", "concurrency_fit", "quality_delta_measurement"},
    "always-deep-research": ALL_BACKEND_CAPS - {"selective_activation", "overhead_budget", "low_operator_burden"},
    "worker-majority-vote": ALL_BACKEND_CAPS | {"worker_majority_authority"},
    "unbounded-parallelism": ALL_BACKEND_CAPS - {"bounded_parallelism", "disjoint_writes", "fallback_path", "overhead_budget"},
    "thin-validation-layer": ALL_ARCHITECTURE_CAPS,
    "new-hypothesis-lab-court-mode": ALL_ARCHITECTURE_CAPS - {"no_new_court_mode", "simple_mental_model", "low_churn"},
    "expand-workflow-run-schema": ALL_ARCHITECTURE_CAPS - {"preserves_workflow_run", "no_schema_churn", "low_churn"},
    "docs-only-guidance": ALL_ARCHITECTURE_CAPS - {"fills_measurement_gap", "instruction_guard", "unit_tests", "replayable"},
    "integrated-quality-gate-only": ALL_ARCHITECTURE_CAPS - {"instruction_guard", "docs_clear", "simple_mental_model"},
    "data-file-driven-matrix": ALL_ARCHITECTURE_CAPS - {"low_churn", "simple_mental_model"},
    "external-runtime-adapter": ALL_ARCHITECTURE_CAPS - {"no_new_runtime", "replayable", "low_churn", "simple_mental_model"},
    "separate-runtime-database": ALL_ARCHITECTURE_CAPS - {"low_churn", "no_new_runtime", "simple_mental_model"},
    "replace-deterministic-benchmarks-with-llm-judge": ALL_ARCHITECTURE_CAPS - {"replayable", "no_schema_churn", "unit_tests"},
    "script-and-docs-with-instruction-guard": ALL_ARCHITECTURE_CAPS - {"low_churn"},
}


def measurement(metric: str, threshold: str, method: str) -> dict[str, str]:
    return {
        "performance_metric": metric,
        "pass_threshold": threshold,
        "method": method,
    }


def candidate(
    area_id: str,
    candidate_id: str,
    hypothesis: str,
    implementation: str,
    scores: dict[str, float],
    *,
    metric: str,
    threshold: str,
    method: str,
    refs: list[str] | None = None,
    hard_gates: dict[str, bool] | None = None,
) -> Candidate:
    gates = {gate: True for gate in HARD_GATES}
    if hard_gates:
        gates.update(hard_gates)
    default_refs = refs or [
        "docs/sejong/VALIDATION.md",
        "docs/sejong/WORKFLOW_RUN.md",
        "docs/sejong/SEUNGJEONGWON_EXECUTOR.md",
    ]
    return Candidate(
        area_id=area_id,
        id=candidate_id,
        hypothesis=hypothesis,
        implementation=implementation,
        measurement=measurement(metric, threshold, method),
        metrics=scores,
        evidence_refs=default_refs,
        implementation_refs=["docs/sejong/scripts/benchmark_orchestrator_hypothesis_matrix.py"],
        verification_refs=[
            "docs/sejong/scripts/test_orchestrator_hypothesis_matrix.py",
            "docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets",
        ],
        hard_gates=gates,
    )


def scores(
    outcome: float,
    guardrail: float,
    observability: float,
    reliability: float,
    efficiency: float,
    parallelism: float,
    experience: float,
) -> dict[str, float]:
    return {
        "outcome_quality": outcome,
        "guardrail_integrity": guardrail,
        "observability_diagnosability": observability,
        "reliability_reproducibility": reliability,
        "efficiency_cost": efficiency,
        "parallelism_fit": parallelism,
        "human_developer_experience": experience,
    }


def built_in_candidates() -> list[Candidate]:
    return [
        candidate(
            "hypothesis_selection_gate",
            "ranked-matrix-with-tie-breakers",
            "Evaluate at least ten candidate tactics per improvement area, then adopt the top passing tactic with deterministic tie-breakers.",
            "Add a deterministic hypothesis matrix benchmark with weighted metrics, hard gates, and adoption output.",
            scores(0.95, 1.00, 0.97, 0.96, 0.86, 0.82, 0.94),
            metric="weighted multi-metric candidate score plus unresolved-tie count",
            threshold=f"score >= {MIN_OVERALL_SCORE} and unresolved ties == 0",
            method="Score all candidates against identical metrics, then apply tie_breaker_dimensions.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "elo-tournament-only",
            "Use pairwise tournament rankings for every improvement idea.",
            "Rank hypotheses by pairwise wins and Elo-style ordering.",
            scores(0.90, 1.00, 0.80, 0.78, 0.70, 0.76, 0.72),
            metric="rank correlation and reproducibility under replay",
            threshold="stable top candidate across replayed seed matrices",
            method="Compare pairwise ordering against deterministic metric scorecards.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "llm-judge-only",
            "Let a judge model decide which hypothesis should be adopted.",
            "Record a judge verdict in Sillok without deterministic score decomposition.",
            scores(0.84, 1.00, 0.70, 0.64, 0.72, 0.70, 0.78),
            metric="judge agreement with frozen acceptance criteria",
            threshold="no unsupported promotion and score >= 0.86",
            method="Compare judge choices against frozen candidate metrics and negative controls.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "static-checklist-only",
            "Use a checklist instead of a candidate matrix.",
            "Add a prose checklist to validation docs.",
            scores(0.76, 1.00, 0.78, 0.82, 0.92, 0.52, 0.82),
            metric="discrimination between close candidates",
            threshold="can separate at least two equal primary scores",
            method="Run synthetic ties and verify a unique final candidate.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "workflow-run-overload",
            "Encode all hypothesis selection directly inside workflow-run artifacts.",
            "Extend workflow-run examples with ten-candidate ledgers.",
            scores(0.86, 1.00, 0.88, 0.86, 0.58, 0.82, 0.62),
            metric="schema churn and promotion decision quality",
            threshold="no workflow-run schema break and candidate score >= 0.86",
            method="Compare added schema surface against isolated benchmark surface.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "manual-sillok-ledger",
            "Record every hypothesis manually in an evidence note.",
            "Use Sillok as a handwritten hypothesis ledger.",
            scores(0.78, 1.00, 0.76, 0.70, 0.60, 0.58, 0.74),
            metric="replayability and complete candidate coverage",
            threshold="all candidates can be replayed without conversational memory",
            method="Attempt deterministic replay from the evidence ledger alone.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "pairwise-baseline-candidate-only",
            "Compare one baseline and one candidate at a time.",
            "Reuse outcome-quality comparison without a candidate matrix.",
            scores(0.82, 1.00, 0.82, 0.86, 0.84, 0.54, 0.84),
            metric="coverage of ten-hypothesis user request",
            threshold=">= 10 candidates evaluated per area",
            method="Count candidate coverage before allowing adoption.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "single-best-first",
            "Implement the first strong idea and only compare if it fails.",
            "Skip matrix breadth and run ordinary Seungjeongwon attempts.",
            scores(0.70, 1.00, 0.72, 0.78, 0.94, 0.40, 0.86),
            metric="missed better alternative rate",
            threshold="no untested candidate exceeds adopted score",
            method="Back-test against the full candidate matrix.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "scorecard-without-adoption-ledger",
            "Score every candidate but do not record why the winner was selected.",
            "Print only aggregate area scores.",
            scores(0.88, 1.00, 0.88, 0.90, 0.90, 0.76, 0.80),
            metric="decision auditability",
            threshold="winner includes rejected alternatives and tie-breaker evidence",
            method="Inspect output for selected candidate, rejected candidates, and tie-break fields.",
        ),
        candidate(
            "hypothesis_selection_gate",
            "randomized-ablation",
            "Randomly try candidate variants and keep the first that passes.",
            "Use stochastic ablation order over candidate tactics.",
            scores(0.72, 1.00, 0.62, 0.46, 0.78, 0.66, 0.60),
            metric="replay stability",
            threshold="same input matrix yields same adopted candidate",
            method="Run repeated samples and compare winners.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "lead-owned-bounded-subagents",
            "Use bounded subagents or workers only when scopes are independent and Sejong lead retains synthesis.",
            "Keep worker outputs as evidence and score backend value against overhead and guardrail preservation.",
            scores(0.92, 1.00, 0.94, 0.92, 0.82, 0.96, 0.88),
            metric="quality delta per orchestration overhead",
            threshold="delta >= 0.10 with zero authority violations",
            method="Compare baseline direct work to bounded-worker candidate under workflow-run metrics.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "deterministic-yaml-orchestrator",
            "Use a deterministic routing graph for repeatable multi-agent work.",
            "Model Sejong routing as fixed YAML-like branch definitions.",
            scores(0.84, 1.00, 0.90, 0.94, 0.92, 0.68, 0.72),
            metric="routing reproducibility and flexibility loss",
            threshold="no loss of Uigwe re-entry and score >= 0.86",
            method="Replay routing scenarios and check whether dynamic re-entry remains expressible.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "host-native-team-when-supported",
            "Prefer host-native team messaging when available for peer challenge.",
            "Route independent review lanes through host-native team support, falling back to TeamExecutor.",
            scores(0.90, 1.00, 0.92, 0.88, 0.74, 0.92, 0.84),
            metric="parallel review value minus availability risk",
            threshold="same guardrails pass under fallback backend",
            method="Compare host-native and TeamExecutor evidence shapes against the same criteria.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "team-executor-mailbox-default",
            "Use TeamExecutor mailbox runs for all broad work.",
            "Default broad work to tmux workers coordinated by Sejong state.",
            scores(0.84, 1.00, 0.88, 0.84, 0.56, 0.90, 0.58),
            metric="overplanning rate and overhead",
            threshold="overplanning rate stays below direct baseline",
            method="Run seed scenarios and compare unnecessary team activation.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "manual-shadow-first",
            "Shadow external workflow ideas manually before any automated backend promotion.",
            "Record manual shadow results as non-promotable evidence.",
            scores(0.80, 1.00, 0.84, 0.82, 0.76, 0.62, 0.78),
            metric="shadow evidence quality",
            threshold="manual shadow never becomes promoted backend",
            method="Validate final recommendation and backend provenance.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "codex-mock-workflow",
            "Use Codex mock workflow artifacts to test unproven dynamic workflow ideas.",
            "Represent external workflow concepts as Codex-owned mock artifacts.",
            scores(0.86, 1.00, 0.90, 0.90, 0.82, 0.74, 0.80),
            metric="guardrail coverage before real backend adoption",
            threshold="all protected workflow-run negative controls remain rejected",
            method="Run workflow-run benchmark and comparison gates.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "single-agent-with-escalation",
            "Stay single-agent by default and escalate only after evidence gaps appear.",
            "Start with Sejong direct or Seungjeongwon, then call helpers only on blocked dimensions.",
            scores(0.82, 1.00, 0.86, 0.88, 0.96, 0.54, 0.90),
            metric="quality delta per 1k tokens",
            threshold="no missed-research or missed-review guardrail failure",
            method="Compare against broad cases requiring independent evidence lanes.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "always-deep-research",
            "Use research fan-out for every broad or uncertain request.",
            "Default uncertain work to JangYeongsil fan-out.",
            scores(0.78, 1.00, 0.82, 0.80, 0.46, 0.92, 0.58),
            metric="over-research rate",
            threshold="no direct task incurs avoidable fan-out overhead",
            method="Run seed tasks tagged simple-direct and small-artifact.",
        ),
        candidate(
            "orchestrator_backend_policy",
            "worker-majority-vote",
            "Let workers vote on approval when a majority agrees.",
            "Treat worker consensus as final route or gate approval.",
            scores(0.74, 0.00, 0.74, 0.70, 0.78, 0.90, 0.72),
            metric="authority violation count",
            threshold="authority violations == 0",
            method="Run TeamExecutor invalid-majority and worker-gate fixtures.",
            hard_gates={"keeps_worker_outputs_evidence_only": False},
        ),
        candidate(
            "orchestrator_backend_policy",
            "unbounded-parallelism",
            "Maximize concurrency whenever multiple workers are available.",
            "Launch all possible worker lanes regardless of write scope overlap.",
            scores(0.80, 0.72, 0.72, 0.58, 0.50, 1.00, 0.54),
            metric="write-scope overlap and recovery cost",
            threshold="write scopes remain disjoint and reliability >= 0.85",
            method="Check workflow-run metrics and overlapping write-scope negative controls.",
            hard_gates={"keeps_worker_outputs_evidence_only": True},
        ),
        candidate(
            "architecture_refactor_policy",
            "thin-validation-layer",
            "Add a deterministic hypothesis matrix under validation without changing court-mode architecture.",
            "Keep Sejong, Uigwe, Seungjeongwon, and workflow-run boundaries unchanged; add script, docs, and tests.",
            scores(0.94, 1.00, 0.96, 0.96, 0.90, 0.80, 0.94),
            metric="new measurement coverage minus architecture churn",
            threshold="all benchmarks pass with no new court mode",
            method="Run hypothesis matrix, instruction benchmark, workflow-run gates, and unit tests.",
        ),
        candidate(
            "architecture_refactor_policy",
            "new-hypothesis-lab-court-mode",
            "Create a new court mode dedicated to hypothesis experimentation.",
            "Add HypothesisLab as a new Sejong surface.",
            scores(0.88, 0.60, 0.88, 0.82, 0.52, 0.76, 0.58),
            metric="court-mode boundary stability",
            threshold="does_not_create_new_court_mode == true",
            method="Run instruction-surface checks for unsupported court modes.",
            hard_gates={"does_not_create_new_court_mode": False},
        ),
        candidate(
            "architecture_refactor_policy",
            "expand-workflow-run-schema",
            "Make workflow-run own hypothesis tournaments directly.",
            "Add hypothesis arrays and ranking fields to workflow-run.schema.json.",
            scores(0.88, 1.00, 0.90, 0.86, 0.54, 0.82, 0.62),
            metric="schema churn and backwards compatibility",
            threshold="workflow-run corpus still validates and no migration required",
            method="Run workflow-run schema, corpus audit, and comparison benchmark.",
        ),
        candidate(
            "architecture_refactor_policy",
            "docs-only-guidance",
            "Document the ten-hypothesis rule without a runnable harness.",
            "Add prose guidance to VALIDATION.md only.",
            scores(0.68, 1.00, 0.54, 0.50, 0.98, 0.48, 0.86),
            metric="machine-checkable enforcement",
            threshold="CLI can fail missing ten-candidate coverage",
            method="Attempt to validate a short candidate list and expect failure.",
        ),
        candidate(
            "architecture_refactor_policy",
            "integrated-quality-gate-only",
            "Fold the hypothesis check into the integrated quality gate.",
            "Add one check id to sejong_integrated_quality_gate.py.",
            scores(0.78, 1.00, 0.78, 0.80, 0.86, 0.56, 0.78),
            metric="diagnostic granularity",
            threshold="output identifies winning and rejected hypotheses",
            method="Compare integrated gate output to dedicated matrix output.",
        ),
        candidate(
            "architecture_refactor_policy",
            "data-file-driven-matrix",
            "Represent hypotheses in JSON and validate them with a generic runner.",
            "Add a schema and example corpus for hypothesis matrices.",
            scores(0.92, 1.00, 0.94, 0.94, 0.70, 0.78, 0.80),
            metric="replayability versus new artifact surface",
            threshold="matrix validates and artifact storage policy remains clear",
            method="Validate JSON schema and replay examples.",
        ),
        candidate(
            "architecture_refactor_policy",
            "external-runtime-adapter",
            "Adopt a third-party orchestration runtime for hypothesis trials.",
            "Call an external workflow engine for candidate evaluation.",
            scores(0.82, 0.76, 0.84, 0.78, 0.46, 0.88, 0.50),
            metric="backend provenance and hidden runtime risk",
            threshold="no hidden external runtime and guardrail_integrity == 1.0",
            method="Audit backend provenance and hidden runtime references.",
            hard_gates={"records_reviewable_evidence": False},
        ),
        candidate(
            "architecture_refactor_policy",
            "separate-runtime-database",
            "Persist hypothesis trials in a dedicated local database.",
            "Create a stateful SQLite evidence store for candidate experiments.",
            scores(0.84, 1.00, 0.90, 0.86, 0.42, 0.72, 0.50),
            metric="artifact hygiene and operational overhead",
            threshold="runtime state does not enter repo and overhead is justified",
            method="Audit storage refs and setup requirements.",
        ),
        candidate(
            "architecture_refactor_policy",
            "replace-deterministic-benchmarks-with-llm-judge",
            "Replace string and schema benchmarks with semantic judge review.",
            "Use an LLM judge as the main promotion gate.",
            scores(0.86, 0.92, 0.72, 0.58, 0.64, 0.70, 0.76),
            metric="reproducibility and false-promotion risk",
            threshold="reliability >= 0.85 and hard gates remain deterministic",
            method="Replay the same fixtures and compare pass/fail stability.",
            hard_gates={"records_reviewable_evidence": True},
        ),
        candidate(
            "architecture_refactor_policy",
            "script-and-docs-with-instruction-guard",
            "Add a script, validation docs, and an instruction-surface guard for hypothesis matrices.",
            "Keep implementation small but make the new measurement visible in VALIDATION.md and benchmark_instruction_surface.py.",
            scores(0.93, 1.00, 0.96, 0.96, 0.88, 0.80, 0.92),
            metric="measurement coverage and drift prevention",
            threshold="dedicated script passes and instruction benchmark contains the new contract",
            method="Run the matrix benchmark, its unit tests, and instruction-surface scorecard regeneration.",
        ),
    ]


def run_trials(item: Candidate) -> tuple[dict[str, float], list[dict[str, Any]], list[str]]:
    capabilities = CANDIDATE_CAPABILITIES.get(item.id)
    if capabilities is None:
        return item.metrics, [], []

    relevant_cases = [case for case in TRIAL_CASES if case.area_id == item.area_id]
    missing_dimensions = sorted(set(DIMENSION_WEIGHTS) - {case.dimension for case in relevant_cases})
    trial_results: list[dict[str, Any]] = []
    weighted_passes: dict[str, float] = defaultdict(float)
    weighted_totals: dict[str, float] = defaultdict(float)

    for case in relevant_cases:
        missing_requires = sorted(set(case.requires) - capabilities)
        forbidden_hits = sorted(set(case.forbids) & capabilities)
        passed = not missing_requires and not forbidden_hits
        weighted_totals[case.dimension] += case.weight
        if passed:
            weighted_passes[case.dimension] += case.weight
        trial_results.append(
            {
                "id": case.id,
                "dimension": case.dimension,
                "passed": passed,
                "missing_requires": missing_requires,
                "forbidden_hits": forbidden_hits,
            }
        )

    measured_metrics = {
        dimension: round(weighted_passes[dimension] / weighted_totals[dimension], 4)
        if weighted_totals[dimension]
        else 0.0
        for dimension in DIMENSION_WEIGHTS
    }
    failures = [f"{item.area_id} has no trial cases for dimension: {dimension}" for dimension in missing_dimensions]
    return measured_metrics, trial_results, failures


def candidate_failures(item: Candidate, metrics: dict[str, float], trial_failures: list[str]) -> list[str]:
    failures: list[str] = []
    failures.extend(trial_failures)
    missing_metrics = [dimension for dimension in DIMENSION_WEIGHTS if dimension not in metrics]
    if missing_metrics:
        failures.append(f"missing metrics: {', '.join(missing_metrics)}")
    for dimension, value in metrics.items():
        if dimension not in DIMENSION_WEIGHTS:
            failures.append(f"unexpected metric: {dimension}")
        if not 0.0 <= value <= 1.0:
            failures.append(f"metric {dimension} is outside 0..1: {value}")
    missing_gates = sorted(HARD_GATES - set(item.hard_gates))
    if missing_gates:
        failures.append(f"missing hard gates: {', '.join(missing_gates)}")
    for gate, passed in sorted(item.hard_gates.items()):
        if gate in HARD_GATES and not passed:
            failures.append(f"hard gate failed: {gate}")
    if not item.evidence_refs:
        failures.append("missing evidence_refs")
    if not item.implementation_refs:
        failures.append("missing implementation_refs")
    if not item.verification_refs:
        failures.append("missing verification_refs")
    for field in ["performance_metric", "pass_threshold", "method"]:
        if not item.measurement.get(field):
            failures.append(f"missing measurement.{field}")
    return failures


def weighted_score(metrics: dict[str, float]) -> float:
    return sum(metrics[dimension] * weight for dimension, weight in DIMENSION_WEIGHTS.items())


def dimension_minimum_failures(metrics: dict[str, float]) -> list[str]:
    return [
        f"{dimension} below minimum {minimum}: {metrics.get(dimension, 0.0)}"
        for dimension, minimum in DIMENSION_MINIMUMS.items()
        if metrics.get(dimension, 0.0) < minimum
    ]


def result_for_candidate(item: Candidate, min_overall_score: float) -> dict[str, Any]:
    measured_metrics, trial_results, trial_failures = run_trials(item)
    failures = candidate_failures(item, measured_metrics, trial_failures)
    score = round(weighted_score(measured_metrics), 4) if not [f for f in failures if f.startswith("missing metrics")] else 0.0
    minimum_failures = dimension_minimum_failures(measured_metrics)
    if score < min_overall_score:
        minimum_failures.append(f"overall score below minimum {min_overall_score}: {score}")
    passed = not failures and not minimum_failures
    return {
        "id": item.id,
        "hypothesis": item.hypothesis,
        "implementation": item.implementation,
        "measurement": item.measurement,
        "declared_metrics": item.metrics,
        "metrics": measured_metrics,
        "trial_results": trial_results,
        "score": score,
        "passed": passed,
        "failures": failures + minimum_failures,
        "evidence_refs": item.evidence_refs,
        "implementation_refs": item.implementation_refs,
        "verification_refs": item.verification_refs,
    }


def rank_key(result: dict[str, Any]) -> tuple[Any, ...]:
    metrics = result["metrics"]
    return (
        result["score"],
        *(round(metrics[dimension], 6) for dimension in TIE_BREAKER_DIMENSIONS),
        len(result["evidence_refs"]),
        -len(result["implementation_refs"]),
        result["id"],
    )


def evaluate_area(area_id: str, candidates: list[Candidate], min_hypotheses: int, min_overall_score: float) -> dict[str, Any]:
    candidate_results = [result_for_candidate(item, min_overall_score) for item in candidates]
    passing = [result for result in candidate_results if result["passed"]]
    failures: list[str] = []
    if len(candidates) < min_hypotheses:
        failures.append(f"{area_id} has {len(candidates)} hypotheses; required {min_hypotheses}")
    if not passing:
        failures.append(f"{area_id} has no passing hypothesis")

    primary_groups: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for result in passing:
        primary_groups[result["score"]].append(result)
    tie_groups = {score: group for score, group in primary_groups.items() if len(group) > 1}

    selected: dict[str, Any] | None = None
    unresolved_ties: list[list[str]] = []
    if passing:
        passing_sorted = sorted(passing, key=rank_key, reverse=True)
        selected = passing_sorted[0]
        selected_key = rank_key(selected)
        tied_after_breaker = [result for result in passing_sorted if result is not selected and rank_key(result) == selected_key]
        if tied_after_breaker:
            unresolved_ties.append([selected["id"], *[result["id"] for result in tied_after_breaker]])
            failures.append(f"{area_id} has unresolved tie after tie breakers: {unresolved_ties[-1]}")

    return {
        "area_id": area_id,
        "candidate_count": len(candidates),
        "passing_count": len(passing),
        "passed": not failures,
        "failures": failures,
        "selected": selected,
        "tie_breakers_used": selected is not None and any(selected["score"] == score for score in tie_groups),
        "primary_tie_groups": {str(score): [item["id"] for item in group] for score, group in tie_groups.items()},
        "unresolved_ties": unresolved_ties,
        "candidates": candidate_results,
    }


def evaluate_operational_corpus(selected_by_area: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    failures: list[str] = []

    for case in OPERATIONAL_CORPUS:
        selected = selected_by_area.get(case.area_id)
        selected_id = selected["id"] if selected else None
        capabilities = CANDIDATE_CAPABILITIES.get(selected_id or "", set())
        missing_capabilities = sorted(set(case.required_capabilities) - capabilities)
        missing_refs = [ref for ref in case.evidence_refs if not (REPO_ROOT / ref).exists()]
        passed = (
            selected_id == case.expected_candidate_id
            and not missing_capabilities
            and not missing_refs
        )
        if selected_id != case.expected_candidate_id:
            failures.append(
                f"{case.id} expected {case.expected_candidate_id} for {case.area_id}, selected {selected_id}"
            )
        if missing_capabilities:
            failures.append(f"{case.id} missing selected-candidate capabilities: {', '.join(missing_capabilities)}")
        if missing_refs:
            failures.append(f"{case.id} missing evidence refs: {', '.join(missing_refs)}")
        cases.append(
            {
                "id": case.id,
                "area_id": case.area_id,
                "expected_candidate_id": case.expected_candidate_id,
                "selected_candidate_id": selected_id,
                "passed": passed,
                "evidence_refs": list(case.evidence_refs),
                "required_capabilities": list(case.required_capabilities),
                "missing_capabilities": missing_capabilities,
                "missing_refs": missing_refs,
                "rationale": case.rationale,
            }
        )

    return {
        "passed": not failures,
        "case_count": len(cases),
        "passed_cases": sum(1 for case in cases if case["passed"]),
        "cases": cases,
        "failures": failures,
    }


def evaluate(candidates: list[Candidate], min_hypotheses: int, min_overall_score: float) -> dict[str, Any]:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for item in candidates:
        grouped[item.area_id].append(item)
    area_results = [
        evaluate_area(area_id, grouped[area_id], min_hypotheses, min_overall_score)
        for area_id in sorted(grouped)
    ]
    selected_by_area = {
        area["area_id"]: area["selected"]
        for area in area_results
        if area["selected"] is not None
    }
    operational_corpus = evaluate_operational_corpus(selected_by_area)
    adopted = [
        {
            "area_id": area["area_id"],
            "candidate_id": area["selected"]["id"],
            "score": area["selected"]["score"],
            "tie_breakers_used": area["tie_breakers_used"],
            "implementation": area["selected"]["implementation"],
            "measurement": area["selected"]["measurement"],
        }
        for area in area_results
        if area["selected"] is not None
    ]
    failures = [failure for area in area_results for failure in area["failures"]]
    missing_areas = sorted(REQUIRED_AREA_IDS - set(grouped))
    failures.extend(f"missing required improvement area: {area_id}" for area_id in missing_areas)
    failures.extend(operational_corpus["failures"])
    return {
        "format": FORMAT,
        "passed": not failures,
        "min_hypotheses_per_area": min_hypotheses,
        "min_overall_score": min_overall_score,
        "dimensions": {
            "weights": DIMENSION_WEIGHTS,
            "minimums": DIMENSION_MINIMUMS,
            "tie_breaker_dimensions": TIE_BREAKER_DIMENSIONS,
        },
        "required_area_ids": sorted(REQUIRED_AREA_IDS),
        "area_count": len(area_results),
        "total_hypotheses": sum(area["candidate_count"] for area in area_results),
        "operational_corpus": operational_corpus,
        "adopted_hypotheses": adopted,
        "area_results": area_results,
        "failures": failures,
    }


def markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# Orchestrator Hypothesis Matrix",
        f"- Passed: `{report['passed']}`",
        f"- Areas: `{report['area_count']}`",
        f"- Total hypotheses evaluated: `{report['total_hypotheses']}`",
        f"- Operational corpus: `{report['operational_corpus']['passed_cases']}/{report['operational_corpus']['case_count']}`",
        f"- Minimum hypotheses per area: `{report['min_hypotheses_per_area']}`",
        f"- Minimum score: `{report['min_overall_score']}`",
    ]
    for adopted in report["adopted_hypotheses"]:
        lines.append(
            f"- `{adopted['area_id']}` -> `{adopted['candidate_id']}` "
            f"score `{adopted['score']}` tie_breakers_used `{adopted['tie_breakers_used']}`"
        )
    if report["failures"]:
        lines.append("## Failures")
        lines.extend(f"- {failure}" for failure in report["failures"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark King Sejong orchestrator improvement hypotheses.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--require-targets", action="store_true", help="Exit non-zero unless all matrix targets pass.")
    parser.add_argument("--min-hypotheses-per-area", type=int, default=MIN_HYPOTHESES_PER_AREA)
    parser.add_argument("--min-overall-score", type=float, default=MIN_OVERALL_SCORE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(built_in_candidates(), args.min_hypotheses_per_area, args.min_overall_score)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(markdown_summary(report).rstrip())
    if args.require_targets and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
