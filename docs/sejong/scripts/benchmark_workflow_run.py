#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from typing import Any

from sejong_workflow_run import FORBIDDEN_AUTHORITY_TERMS, RUN_FORMAT, run_failures


def timestamp() -> str:
    return "2026-05-29T00:00:00Z"


def base_run(
    *,
    run_id: str,
    workflow_kind: str,
    backend: str,
    mode: str,
    mapped_surfaces: list[str],
    final_recommendation: str,
    comparison_recommendation: str,
    quality_delta: float,
    overhead_ratio: float = 1.0,
) -> dict[str, Any]:
    return {
        "format": RUN_FORMAT,
        "run_id": run_id,
        "repo_root": "/tmp/sejong-workflow-run-benchmark",
        "status": "completed",
        "workflow_kind": workflow_kind,
        "workflow_name": run_id,
        "mapped_surfaces": mapped_surfaces,
        "backend": backend,
        "backend_provenance": {
            "migration_type": {
                "codex_native_subagents": "codex_native",
                "codex_mock_workflow": "codex_mock",
                "host_native_team": "host_native",
                "team_executor": "team_executor",
                "manual_shadow": "manual_shadow",
            }.get(backend, "approved_other"),
            "non_claude_runtime": True,
            "summary": "Workflow concept is evaluated as a Codex-owned, host-native, TeamExecutor, manual, or approved mock backend.",
            "command_refs": [
                "docs/sejong/scripts/benchmark_workflow_run.py"
            ],
        },
        "mode": mode,
        "artifact_storage": {
            "scope": "external",
            "ref": "${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}",
        },
        "source_of_truth_refs": [
            "docs/sejong/DISCIPLINE_GATES.md",
            "docs/sejong/VALIDATION.md",
        ],
        "success_criteria": [
            "The candidate is evaluated against the same acceptance criteria as the baseline.",
            "No worker or backend claims court authority.",
        ],
        "forbidden_authority_claims": list(FORBIDDEN_AUTHORITY_TERMS),
        "workers": [
            {
                "worker_id": "worker-1",
                "role": "bounded evidence lane",
                "scope": "Collect and cross-check evidence only.",
                "allowed_outputs": [
                    "known/inferred/unknown evidence only",
                    "discarded claims with source references",
                ],
                "write_scope": [
                    "workflow-run.evidence_ledger.worker-1"
                ],
                "status": "completed",
            }
        ],
        "evidence_ledger": [
            {
                "evidence_id": "source-1",
                "kind": "source_ref",
                "summary": "Source-of-truth docs were checked before promotion.",
                "refs": [
                    "docs/sejong/DISCIPLINE_GATES.md"
                ],
                "status": "supported",
            },
            {
                "evidence_id": "verification-1",
                "kind": "verification_ref",
                "summary": "Workflow-run helper validated the artifact.",
                "refs": [
                    "python3 docs/sejong/scripts/sejong_workflow_run.py check"
                ],
                "status": "verified",
            },
        ],
        "quality_comparison": {
            "baseline_result_ref": f"baseline:{run_id}",
            "candidate_result_ref": f"candidate:{run_id}",
            "acceptance_criteria": [
                "Compare final result quality, not just routing or worker activity."
            ],
            "outcome_quality_delta": quality_delta,
            "overhead_ratio": overhead_ratio,
            "recommendation": comparison_recommendation,
        },
        "metrics": {
            "worker_count": 1,
            "max_concurrency": 1,
            "unsupported_claim_count": 0,
            "token_or_cost_overhead_ref": f"benchmark:{run_id}:overhead",
            "write_scopes_disjoint": True,
        },
        "verification_evidence": [
            "workflow-run benchmark case passed"
        ],
        "violations": [],
        "final_recommendation": final_recommendation,
        "created_at": timestamp(),
        "updated_at": timestamp(),
    }


def valid_cases() -> list[dict[str, Any]]:
    deep_research = base_run(
        run_id="deep-research-shadow-kept",
        workflow_kind="deep_research",
        backend="manual_shadow",
        mode="shadow",
        mapped_surfaces=["jangyeongsil", "sillok"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.04,
        overhead_ratio=1.3,
    )
    deep_research["evidence_ledger"].append(
        {
            "evidence_id": "cross-check-1",
            "kind": "cross_check",
            "summary": "Claims were cross-checked across source-of-truth docs.",
            "refs": [
                "docs/sejong/VALIDATION.md"
            ],
            "status": "verified",
        }
    )
    deep_research["evidence_ledger"].append(
        {
            "evidence_id": "discarded-claim-1",
            "kind": "discarded_claim",
            "summary": "Unverified worker consensus was discarded as authority evidence.",
            "refs": [
                "docs/sejong/TEAM_EXECUTOR.md"
            ],
            "status": "rejected",
        }
    )

    promoted_mock = base_run(
        run_id="dynamic-codex-mock-promoted",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="promoted_backend",
        mapped_surfaces=["uigwe", "seungjeongwon"],
        final_recommendation="promote",
        comparison_recommendation="promote",
        quality_delta=0.18,
        overhead_ratio=1.15,
    )

    rejected_authority = base_run(
        run_id="team-backend-authority-rejected",
        workflow_kind="team_backend",
        backend="team_executor",
        mode="limited_backend",
        mapped_surfaces=["jiphyeonjeon", "seungjeongwon"],
        final_recommendation="reject",
        comparison_recommendation="reject",
        quality_delta=-0.12,
        overhead_ratio=1.6,
    )
    rejected_authority["evidence_ledger"].append(
        {
            "evidence_id": "authority-violation-1",
            "kind": "authority_violation",
            "summary": "A worker claimed final synthesis and the candidate was rejected.",
            "refs": [
                "worker:critic"
            ],
            "status": "violating",
        }
    )
    rejected_authority["violations"].append("worker:critic claimed final synthesis")

    ultracode_style = base_run(
        run_id="ultracode-style-shadow-kept",
        workflow_kind="ultracode_style",
        backend="codex_native_subagents",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.03,
        overhead_ratio=1.8,
    )
    ultracode_style["workers"].extend(
        [
            {
                "worker_id": "worker-2",
                "role": "cost lane",
                "scope": "Estimate overhead and operational cost.",
                "allowed_outputs": [
                    "cost and overhead observations"
                ],
                "write_scope": [
                    "workflow-run.evidence_ledger.worker-2"
                ],
                "status": "completed",
            },
            {
                "worker_id": "worker-3",
                "role": "verification lane",
                "scope": "Check that verification remains lead-owned.",
                "allowed_outputs": [
                    "verification findings only"
                ],
                "write_scope": [
                    "workflow-run.evidence_ledger.worker-3"
                ],
                "status": "completed",
            },
        ]
    )
    ultracode_style["metrics"]["worker_count"] = len(ultracode_style["workers"])
    ultracode_style["metrics"]["max_concurrency"] = 3
    ultracode_style["evidence_ledger"].append(
        {
            "evidence_id": "cost-1",
            "kind": "cost",
            "summary": "Candidate quality improved slightly but overhead remained high.",
            "refs": [
                "benchmark:ultracode-style-shadow-kept"
            ],
            "status": "supported",
        }
    )
    return [deep_research, promoted_mock, rejected_authority, ultracode_style]


def invalid_cases() -> list[tuple[dict[str, Any], list[str]]]:
    hidden_claude = base_run(
        run_id="hidden-claude-backend",
        workflow_kind="dynamic_workflow",
        backend="claude_code_workflow",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )

    promote_with_violation = base_run(
        run_id="promote-with-violation",
        workflow_kind="team_backend",
        backend="team_executor",
        mode="promoted_backend",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="promote",
        comparison_recommendation="promote",
        quality_delta=0.2,
    )
    promote_with_violation["evidence_ledger"].append(
        {
            "evidence_id": "authority-violation-1",
            "kind": "authority_violation",
            "summary": "A worker claimed Uigwe gate approval.",
            "refs": [
                "worker:planner"
            ],
            "status": "violating",
        }
    )
    promote_with_violation["violations"].append("worker:planner claimed Uigwe gate approval")

    missing_comparison = base_run(
        run_id="completed-without-comparison",
        workflow_kind="deep_research",
        backend="manual_shadow",
        mode="shadow",
        mapped_surfaces=["jangyeongsil"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="unknown",
        quality_delta=0,
    )
    missing_comparison["quality_comparison"]["baseline_result_ref"] = "unrecorded"

    high_overhead_promotion = base_run(
        run_id="high-overhead-weak-promotion",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="promoted_backend",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="promote",
        comparison_recommendation="promote",
        quality_delta=0.0001,
        overhead_ratio=999,
    )

    weak_positive_delta_promotion = base_run(
        run_id="weak-positive-delta-promotion",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="promoted_backend",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="promote",
        comparison_recommendation="promote",
        quality_delta=0.01,
        overhead_ratio=1.0,
    )

    empty_acceptance_criteria = base_run(
        run_id="empty-acceptance-criteria",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )
    empty_acceptance_criteria["quality_comparison"]["acceptance_criteria"] = []

    final_recommendation_mismatch = base_run(
        run_id="final-recommendation-mismatch",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="reject",
        comparison_recommendation="promote",
        quality_delta=0.2,
    )

    other_without_provenance = base_run(
        run_id="other-without-provenance",
        workflow_kind="dynamic_workflow",
        backend="other",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )
    other_without_provenance["backend_provenance"]["summary"] = ""
    other_without_provenance["backend_provenance"]["command_refs"] = []

    weak_other_provenance = base_run(
        run_id="weak-other-provenance",
        workflow_kind="dynamic_workflow",
        backend="other",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )
    weak_other_provenance["backend_provenance"]["summary"] = "trust me"
    weak_other_provenance["backend_provenance"]["command_refs"] = ["trust me"]

    manual_shadow_promoted = base_run(
        run_id="manual-shadow-promoted",
        workflow_kind="dynamic_workflow",
        backend="manual_shadow",
        mode="promoted_backend",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="promote",
        comparison_recommendation="promote",
        quality_delta=0.2,
    )

    duplicate_ids = base_run(
        run_id="duplicate-worker-and-evidence",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )
    duplicate_ids["workers"].append(deepcopy(duplicate_ids["workers"][0]))
    duplicate_ids["evidence_ledger"].append(deepcopy(duplicate_ids["evidence_ledger"][0]))

    bad_surface = base_run(
        run_id="unsupported-surface",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="shadow",
        mapped_surfaces=["claude-court"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )

    overlapping_write_scopes = base_run(
        run_id="overlapping-write-scopes",
        workflow_kind="team_backend",
        backend="team_executor",
        mode="limited_backend",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.01,
    )
    overlapping_write_scopes["workers"].append(
        {
            "worker_id": "worker-2",
            "role": "bounded lane",
            "scope": "Try to write the same evidence scope.",
            "allowed_outputs": [
                "known/inferred/unknown evidence only"
            ],
            "write_scope": [
                "workflow-run.evidence_ledger.worker-1"
            ],
            "status": "completed",
        }
    )
    overlapping_write_scopes["metrics"]["worker_count"] = 2
    overlapping_write_scopes["metrics"]["max_concurrency"] = 2

    return [
        (hidden_claude, ["unsupported backend"]),
        (promote_with_violation, ["promote requires no violations", "promote cannot include authority violation evidence"]),
        (missing_comparison, ["completed run requires quality comparison recommendation", "completed run requires baseline and candidate result refs"]),
        (high_overhead_promotion, ["overhead_ratio > 1.25"]),
        (weak_positive_delta_promotion, ["promote requires outcome_quality_delta >= 0.10"]),
        (empty_acceptance_criteria, ["quality_comparison acceptance_criteria must be a non-empty list once recorded"]),
        (final_recommendation_mismatch, ["completed run final_recommendation must match quality_comparison recommendation"]),
        (other_without_provenance, ["backend_provenance summary must be a non-empty string", "backend_provenance command_refs must be a non-empty list"]),
        (weak_other_provenance, ["backend other requires a specific backend_provenance summary", "backend other requires reviewable backend_provenance command_refs"]),
        (manual_shadow_promoted, ["manual_shadow cannot be promoted_backend"]),
        (duplicate_ids, ["duplicate worker_id", "duplicate evidence_id"]),
        (bad_surface, ["unsupported mapped surface"]),
        (overlapping_write_scopes, ["worker write scopes overlap"]),
    ]


def large_run(worker_count: int, evidence_count: int) -> dict[str, Any]:
    data = base_run(
        run_id="large-scale-workflow-run",
        workflow_kind="dynamic_workflow",
        backend="codex_mock_workflow",
        mode="shadow",
        mapped_surfaces=["seungjeongwon"],
        final_recommendation="keep_shadowing",
        comparison_recommendation="keep_shadowing",
        quality_delta=0.02,
        overhead_ratio=2.0,
    )
    data["workers"] = [
        {
            "worker_id": f"worker-{idx}",
            "role": "bounded lane",
            "scope": f"Independent lane {idx}",
            "allowed_outputs": [
                "known/inferred/unknown evidence only"
            ],
            "write_scope": [
                f"workflow-run.evidence_ledger.worker-{idx}"
            ],
            "status": "completed",
        }
        for idx in range(worker_count)
    ]
    data["evidence_ledger"] = [
        {
            "evidence_id": f"evidence-{idx}",
            "kind": "verification_ref" if idx == 0 else ("cross_check" if idx % 2 else "finding"),
            "summary": f"Large-run evidence item {idx}",
            "refs": [
                f"benchmark:large-run:{idx}"
            ],
            "status": "verified" if idx % 2 else "supported",
        }
        for idx in range(evidence_count)
    ]
    data["metrics"] = {
        "worker_count": worker_count,
        "max_concurrency": min(worker_count, 64),
        "unsupported_claim_count": 0,
        "token_or_cost_overhead_ref": "benchmark:large-run:overhead",
        "write_scopes_disjoint": True,
    }
    return data


def evaluate_cases() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for data in valid_cases():
        failures = run_failures(data)
        results.append(
            {
                "id": data["run_id"],
                "expect": "valid",
                "passed": not failures,
                "failures": failures,
            }
        )
    for data, expected_fragments in invalid_cases():
        failures = run_failures(data)
        joined = "\n".join(failures)
        expected_failures_present = all(fragment in joined for fragment in expected_fragments)
        results.append(
            {
                "id": data["run_id"],
                "expect": "invalid",
                "passed": bool(failures) and expected_failures_present,
                "failures": failures,
                "expected_failure_fragments": expected_fragments,
            }
        )
    return results


def evaluate_performance(worker_count: int, evidence_count: int, max_seconds: float) -> dict[str, Any]:
    data = large_run(worker_count, evidence_count)
    started = time.perf_counter()
    failures = run_failures(data)
    elapsed = time.perf_counter() - started
    return {
        "id": "large-scale-linear-validation",
        "worker_count": worker_count,
        "evidence_count": evidence_count,
        "max_seconds": max_seconds,
        "elapsed_seconds": round(elapsed, 6),
        "passed": not failures and elapsed <= max_seconds,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Sejong workflow-run use cases and validation performance.")
    parser.add_argument("--worker-count", type=int, default=1000)
    parser.add_argument("--evidence-count", type=int, default=2000)
    parser.add_argument("--max-seconds", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", help="Emit the full result as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case_results = evaluate_cases()
    perf_result = evaluate_performance(args.worker_count, args.evidence_count, args.max_seconds)
    passed = all(result["passed"] for result in case_results) and perf_result["passed"]
    result = {
        "format": "sejong.workflow-run-benchmark/v0.1-draft",
        "passed": passed,
        "cases": case_results,
        "performance": perf_result,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "workflow_run_benchmark "
            f"{'ok' if passed else 'failed'}: "
            f"cases={sum(1 for item in case_results if item['passed'])}/{len(case_results)} "
            f"performance={perf_result['elapsed_seconds']}s/{perf_result['max_seconds']}s "
            f"workers={perf_result['worker_count']} evidence={perf_result['evidence_count']}"
        )
        if not passed:
            for item in case_results:
                if not item["passed"]:
                    print(f"failure: {item['id']} -> {item['failures']}", file=sys.stderr)
            if not perf_result["passed"]:
                print(f"failure: {perf_result['id']} -> {perf_result}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
