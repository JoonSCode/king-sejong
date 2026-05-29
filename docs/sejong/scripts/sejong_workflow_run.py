#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import path_contains_or_equals, resolve_path


RUN_FORMAT = "sejong.workflow-run/v0.1-draft"
STATUSES = {"shadow", "active", "completed", "blocked", "invalidated", "failed"}
WORKFLOW_KINDS = {"dynamic_workflow", "deep_research", "ultracode_style", "team_backend", "other"}
BACKENDS = {"codex_native_subagents", "codex_mock_workflow", "host_native_team", "team_executor", "manual_shadow", "other"}
BACKEND_MIGRATION_TYPES = {
    "codex_native_subagents": "codex_native",
    "codex_mock_workflow": "codex_mock",
    "host_native_team": "host_native",
    "team_executor": "team_executor",
    "manual_shadow": "manual_shadow",
}
MIGRATION_TYPES = set(BACKEND_MIGRATION_TYPES.values()) | {"approved_other"}
MODES = {"shadow", "limited_backend", "promoted_backend"}
SURFACES = {"sejong", "jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon", "sillok", "danjong", "sejong-direct"}
WORKER_STATUSES = {"pending", "active", "completed", "blocked", "failed"}
EVIDENCE_KINDS = {"source_ref", "claim", "discarded_claim", "cross_check", "verification_ref", "cost", "finding", "authority_violation"}
EVIDENCE_STATUSES = {"open", "supported", "rejected", "verified", "violating"}
RECOMMENDATIONS = {"promote", "reject", "keep_shadowing", "unknown"}
FORBIDDEN_AUTHORITY_TERMS = (
    "uigwe gate approval",
    "final synthesis",
    "final verification",
    "consensus approval",
    "majority-vote authority",
)
AUTHORITY_CLAIM_PATTERNS = FORBIDDEN_AUTHORITY_TERMS + (
    "approve uigwe gate",
    "approves uigwe gate",
    "approves gates",
    "approval gate",
    "final decision",
    "consensus accepted",
    "worker majority approved",
    "majority approved",
)
HIDDEN_CLAUDE_RUNTIME_PATTERNS = (
    "claude cli",
    "claude api",
    "claude workflow runtime",
    "external claude workflow",
    "claude_code_workflow",
    "claude backend",
    "=claude",
)
MIN_PROMOTION_QUALITY_DELTA = 0.10
GENERIC_RESULT_REFS = {"baseline", "candidate", "unrecorded", "trust me", "self-attested"}
WEAK_PROVENANCE_SUMMARIES = {"trust me", "self-attested", "manual", "approved", "ok"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quality_comparison() -> dict[str, Any]:
    return {
        "baseline_result_ref": "unrecorded",
        "candidate_result_ref": "unrecorded",
        "acceptance_criteria": [],
        "outcome_quality_delta": 0,
        "overhead_ratio": 1,
        "recommendation": "unknown",
    }


def backend_provenance_for(backend: str, summary: str | None = None, command_refs: list[str] | None = None) -> dict[str, Any]:
    migration_type = BACKEND_MIGRATION_TYPES.get(backend, "approved_other")
    default_summary = f"{backend} is evaluated as a Codex-owned, host-native, TeamExecutor, manual, or approved mock backend."
    default_command_refs = ["docs/sejong/scripts/sejong_workflow_run.py"]
    if backend == "other":
        default_summary = ""
        default_command_refs = []
    return {
        "migration_type": migration_type,
        "non_claude_runtime": True,
        "summary": summary if summary is not None else default_summary,
        "command_refs": command_refs if command_refs is not None else default_command_refs,
    }


def metrics_for(worker_count: int = 0, max_concurrency: int = 0) -> dict[str, Any]:
    return {
        "worker_count": worker_count,
        "max_concurrency": max_concurrency,
        "unsupported_claim_count": 0,
        "token_or_cost_overhead_ref": "not-yet-measured",
        "write_scopes_disjoint": True,
    }


def artifact_storage_for(promoted_artifact_ref: str | None = None) -> dict[str, Any]:
    if promoted_artifact_ref:
        return {
            "scope": "promoted_repo_artifact",
            "ref": promoted_artifact_ref,
        }
    return {
        "scope": "external",
        "ref": "${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}",
    }


def list_field_failures(data: dict[str, Any], field: str) -> list[str]:
    if field not in data:
        return []
    value = data.get(field)
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} entries must be non-empty strings"]
    return []


def reviewable_ref(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized or normalized.casefold() in GENERIC_RESULT_REFS:
        return False
    return any(marker in normalized for marker in (":", "/", "."))


def weak_provenance_summary(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip()
    return len(normalized) < 24 or normalized.casefold() in WEAK_PROVENANCE_SUMMARIES


def forbidden_authority_output(value: str) -> str | None:
    normalized = value.casefold()
    for term in AUTHORITY_CLAIM_PATTERNS:
        if term in normalized:
            return term
    return None


def iter_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_text_values(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(iter_text_values(item))
        return result
    return []


def hidden_claude_runtime_ref(value: Any) -> str | None:
    for text in iter_text_values(value):
        normalized = text.casefold()
        for pattern in HIDDEN_CLAUDE_RUNTIME_PATTERNS:
            if pattern in normalized:
                return pattern
    return None


def is_date_time(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def run_failures(data: dict[str, Any]) -> list[str]:
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
        "backend_provenance",
        "mode",
        "artifact_storage",
        "source_of_truth_refs",
        "success_criteria",
        "forbidden_authority_claims",
        "workers",
        "evidence_ledger",
        "quality_comparison",
        "metrics",
        "verification_evidence",
        "violations",
        "final_recommendation",
        "created_at",
        "updated_at",
    ]
    for field in required:
        if field not in data:
            failures.append(f"missing {field}")
    for field in data:
        if field not in required:
            failures.append(f"unexpected top-level field: {field}")
    hidden_claude = hidden_claude_runtime_ref(data)
    if hidden_claude:
        failures.append(f"hidden Claude runtime reference is forbidden: {hidden_claude}")
    if data.get("format") != RUN_FORMAT:
        failures.append(f"unexpected format: {data.get('format')}")
    if data.get("status") not in STATUSES:
        failures.append(f"unsupported run status: {data.get('status')}")
    if data.get("workflow_kind") not in WORKFLOW_KINDS:
        failures.append(f"unsupported workflow kind: {data.get('workflow_kind')}")
    if data.get("backend") not in BACKENDS:
        failures.append(f"unsupported backend: {data.get('backend')}")
    if data.get("mode") not in MODES:
        failures.append(f"unsupported mode: {data.get('mode')}")
    if data.get("final_recommendation") not in RECOMMENDATIONS:
        failures.append(f"unsupported final recommendation: {data.get('final_recommendation')}")
    if not is_date_time(data.get("created_at")):
        failures.append("created_at must be a date-time string")
    if not is_date_time(data.get("updated_at")):
        failures.append("updated_at must be a date-time string")

    for field in (
        "mapped_surfaces",
        "source_of_truth_refs",
        "success_criteria",
        "forbidden_authority_claims",
        "workers",
        "evidence_ledger",
        "verification_evidence",
        "violations",
    ):
        if field in data and not isinstance(data.get(field), list):
            failures.append(f"{field} must be a list")
    for field in ("source_of_truth_refs", "success_criteria", "forbidden_authority_claims", "verification_evidence", "violations"):
        failures.extend(list_field_failures(data, field))
    forbidden_claims = set(data.get("forbidden_authority_claims") or [])
    for claim in FORBIDDEN_AUTHORITY_TERMS:
        if claim not in forbidden_claims:
            failures.append(f"forbidden_authority_claims missing canonical claim: {claim}")

    provenance = data.get("backend_provenance")
    if not isinstance(provenance, dict):
        failures.append("backend_provenance must be an object")
        provenance = {}
    else:
        allowed = {"migration_type", "non_claude_runtime", "summary", "command_refs"}
        for field in provenance:
            if field not in allowed:
                failures.append(f"backend_provenance has unexpected field: {field}")
        migration_type = provenance.get("migration_type")
        if migration_type not in MIGRATION_TYPES:
            failures.append(f"unsupported backend migration type: {migration_type}")
        expected_migration = BACKEND_MIGRATION_TYPES.get(data.get("backend"))
        if expected_migration and migration_type != expected_migration:
            failures.append(f"backend {data.get('backend')} requires migration_type {expected_migration}")
        if data.get("backend") == "other" and migration_type != "approved_other":
            failures.append("backend other requires migration_type approved_other")
        if provenance.get("non_claude_runtime") is not True:
            failures.append("backend_provenance non_claude_runtime must be true")
        if not isinstance(provenance.get("summary"), str) or not provenance.get("summary"):
            failures.append("backend_provenance summary must be a non-empty string")
        if not isinstance(provenance.get("command_refs"), list) or not provenance.get("command_refs"):
            failures.append("backend_provenance command_refs must be a non-empty list")
        elif any(not isinstance(ref, str) or not ref for ref in provenance.get("command_refs") or []):
            failures.append("backend_provenance command_refs entries must be non-empty strings")
        elif data.get("backend") == "other" and any(not reviewable_ref(ref) for ref in provenance.get("command_refs") or []):
            failures.append("backend other requires reviewable backend_provenance command_refs")
        if data.get("backend") == "other" and weak_provenance_summary(provenance.get("summary")):
            failures.append("backend other requires a specific backend_provenance summary")
        if data.get("mode") == "promoted_backend" and data.get("backend") == "manual_shadow":
            failures.append("manual_shadow cannot be promoted_backend; migrate to a Codex-native or mock backend before promotion")

    artifact_storage = data.get("artifact_storage")
    if not isinstance(artifact_storage, dict):
        failures.append("artifact_storage must be an object")
        artifact_storage = {}
    else:
        allowed_artifact_storage_fields = {"scope", "ref"}
        for field in artifact_storage:
            if field not in allowed_artifact_storage_fields:
                failures.append(f"artifact_storage has unexpected field: {field}")
        if artifact_storage.get("scope") not in {"external", "promoted_example", "promoted_repo_artifact"}:
            failures.append(f"unsupported artifact_storage scope: {artifact_storage.get('scope')}")
        if not isinstance(artifact_storage.get("ref"), str) or not artifact_storage.get("ref"):
            failures.append("artifact_storage ref must be a non-empty string")

    surfaces = data.get("mapped_surfaces") or []
    if not surfaces:
        failures.append("mapped_surfaces must not be empty")
    for surface in surfaces:
        if surface not in SURFACES:
            failures.append(f"unsupported mapped surface: {surface}")
    if not data.get("source_of_truth_refs"):
        failures.append("source_of_truth_refs must not be empty")
    if not data.get("success_criteria"):
        failures.append("success_criteria must not be empty")

    worker_ids: set[str] = set()
    write_scope_owners: dict[str, str] = {}
    overlapping_write_scopes: list[str] = []
    for worker in data.get("workers") or []:
        worker_id = worker.get("worker_id") if isinstance(worker, dict) else None
        if not isinstance(worker, dict):
            failures.append("worker entry must be an object")
            continue
        allowed_worker_fields = {"worker_id", "role", "scope", "allowed_outputs", "write_scope", "status"}
        for field in worker:
            if field not in allowed_worker_fields:
                failures.append(f"worker {worker_id or '<missing>'} has unexpected field: {field}")
        for field in ("worker_id", "role", "scope", "allowed_outputs", "write_scope", "status"):
            if field not in worker:
                failures.append(f"worker {worker_id or '<missing>'} missing {field}")
        if worker_id in worker_ids:
            failures.append(f"duplicate worker_id: {worker_id}")
        if worker_id:
            worker_ids.add(worker_id)
        if worker.get("status") not in WORKER_STATUSES:
            failures.append(f"worker {worker_id or '<missing>'} has unsupported status: {worker.get('status')}")
        for field in ("allowed_outputs", "write_scope"):
            if not isinstance(worker.get(field), list):
                failures.append(f"worker {worker_id or '<missing>'} {field} must be a list")
        for text_field in ("role", "scope"):
            value = worker.get(text_field)
            if isinstance(value, str):
                forbidden = forbidden_authority_output(value)
                if forbidden:
                    failures.append(f"worker {worker_id or '<missing>'} claims forbidden authority in {text_field}: {forbidden}")
        for output in worker.get("allowed_outputs") or []:
            if not isinstance(output, str) or not output:
                failures.append(f"worker {worker_id or '<missing>'} allowed_outputs entries must be non-empty strings")
                continue
            forbidden = forbidden_authority_output(output)
            if forbidden:
                failures.append(f"worker {worker_id or '<missing>'} claims forbidden authority: {forbidden}")
        for scope in worker.get("write_scope") or []:
            if not isinstance(scope, str) or not scope:
                failures.append(f"worker {worker_id or '<missing>'} write_scope entries must be non-empty strings")
                continue
            owner = write_scope_owners.get(scope)
            if owner and owner != worker_id:
                overlapping_write_scopes.append(scope)
            else:
                write_scope_owners[scope] = worker_id or "<missing>"
    if overlapping_write_scopes:
        failures.append(f"worker write scopes overlap: {', '.join(sorted(set(overlapping_write_scopes)))}")

    evidence_ids: set[str] = set()
    has_authority_violation = False
    for evidence in data.get("evidence_ledger") or []:
        evidence_id = evidence.get("evidence_id") if isinstance(evidence, dict) else None
        if not isinstance(evidence, dict):
            failures.append("evidence entry must be an object")
            continue
        allowed_evidence_fields = {"evidence_id", "kind", "summary", "refs", "status"}
        for field in evidence:
            if field not in allowed_evidence_fields:
                failures.append(f"evidence {evidence_id or '<missing>'} has unexpected field: {field}")
        for field in ("evidence_id", "kind", "summary", "refs", "status"):
            if field not in evidence:
                failures.append(f"evidence {evidence_id or '<missing>'} missing {field}")
        if evidence_id in evidence_ids:
            failures.append(f"duplicate evidence_id: {evidence_id}")
        if evidence_id:
            evidence_ids.add(evidence_id)
        if evidence.get("kind") not in EVIDENCE_KINDS:
            failures.append(f"evidence {evidence_id or '<missing>'} has unsupported kind: {evidence.get('kind')}")
        if evidence.get("status") not in EVIDENCE_STATUSES:
            failures.append(f"evidence {evidence_id or '<missing>'} has unsupported status: {evidence.get('status')}")
        if not isinstance(evidence.get("refs"), list):
            failures.append(f"evidence {evidence_id or '<missing>'} refs must be a list")
        elif any(not isinstance(ref, str) or not ref for ref in evidence.get("refs") or []):
            failures.append(f"evidence {evidence_id or '<missing>'} refs entries must be non-empty strings")
        if evidence.get("kind") == "authority_violation" or evidence.get("status") == "violating":
            has_authority_violation = True

    comparison = data.get("quality_comparison")
    if not isinstance(comparison, dict):
        failures.append("quality_comparison must be an object")
        comparison = {}
    else:
        allowed_comparison_fields = {
            "baseline_result_ref",
            "candidate_result_ref",
            "acceptance_criteria",
            "outcome_quality_delta",
            "overhead_ratio",
            "recommendation",
        }
        for field in comparison:
            if field not in allowed_comparison_fields:
                failures.append(f"quality_comparison has unexpected field: {field}")
        for field in (
            "baseline_result_ref",
            "candidate_result_ref",
            "acceptance_criteria",
            "outcome_quality_delta",
            "overhead_ratio",
            "recommendation",
        ):
            if field not in comparison:
                failures.append(f"quality_comparison missing {field}")
        if comparison.get("recommendation") not in RECOMMENDATIONS:
            failures.append(f"unsupported quality comparison recommendation: {comparison.get('recommendation')}")
        comparison_recorded = (
            comparison.get("recommendation") != "unknown"
            or data.get("status") == "completed"
            or data.get("final_recommendation") != "unknown"
        )
        if not isinstance(comparison.get("acceptance_criteria"), list):
            failures.append("quality_comparison acceptance_criteria must be a list")
        elif comparison_recorded:
            if not comparison.get("acceptance_criteria"):
                failures.append("quality_comparison acceptance_criteria must be a non-empty list once recorded")
            elif any(not isinstance(item, str) or len(item.strip()) < 12 for item in comparison.get("acceptance_criteria") or []):
                failures.append("quality_comparison acceptance_criteria entries must be task-specific non-empty strings")
        if comparison_recorded:
            baseline_ref = comparison.get("baseline_result_ref")
            candidate_ref = comparison.get("candidate_result_ref")
            if baseline_ref == candidate_ref:
                failures.append("quality_comparison baseline_result_ref and candidate_result_ref must be distinct")
            if not reviewable_ref(baseline_ref):
                failures.append("quality_comparison baseline_result_ref must be a reviewable ref")
            if not reviewable_ref(candidate_ref):
                failures.append("quality_comparison candidate_result_ref must be a reviewable ref")
        if not isinstance(comparison.get("outcome_quality_delta"), (int, float)):
            failures.append("quality_comparison outcome_quality_delta must be a number")
        if not isinstance(comparison.get("overhead_ratio"), (int, float)) or comparison.get("overhead_ratio", -1) < 0:
            failures.append("quality_comparison overhead_ratio must be a non-negative number")

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        failures.append("metrics must be an object")
        metrics = {}
    else:
        allowed_metrics_fields = {
            "worker_count",
            "max_concurrency",
            "unsupported_claim_count",
            "token_or_cost_overhead_ref",
            "write_scopes_disjoint",
        }
        for field in metrics:
            if field not in allowed_metrics_fields:
                failures.append(f"metrics has unexpected field: {field}")
        for field in ("worker_count", "max_concurrency", "unsupported_claim_count"):
            if not isinstance(metrics.get(field), int) or metrics.get(field, -1) < 0:
                failures.append(f"metrics {field} must be a non-negative integer")
        if not isinstance(metrics.get("token_or_cost_overhead_ref"), str) or not metrics.get("token_or_cost_overhead_ref"):
            failures.append("metrics token_or_cost_overhead_ref must be a non-empty string")
        if not isinstance(metrics.get("write_scopes_disjoint"), bool):
            failures.append("metrics write_scopes_disjoint must be a boolean")
        if metrics.get("worker_count") != len(data.get("workers") or []):
            failures.append("metrics worker_count must equal workers length")
        if isinstance(metrics.get("worker_count"), int) and isinstance(metrics.get("max_concurrency"), int):
            if metrics.get("max_concurrency") > metrics.get("worker_count"):
                failures.append("metrics max_concurrency cannot exceed worker_count")
            if metrics.get("worker_count") > 0 and metrics.get("max_concurrency") == 0:
                failures.append("metrics max_concurrency must be positive when workers exist")
        if metrics.get("write_scopes_disjoint") is not True:
            failures.append("metrics write_scopes_disjoint must be true")

    if data.get("mode") == "promoted_backend" and data.get("final_recommendation") != "promote":
        failures.append("promoted_backend mode requires final_recommendation promote")

    if data.get("final_recommendation") == "promote":
        if comparison.get("recommendation") != "promote":
            failures.append("promote requires quality_comparison recommendation promote")
        quality_delta = comparison.get("outcome_quality_delta", 0)
        overhead_ratio = comparison.get("overhead_ratio", 0)
        if quality_delta <= 0:
            failures.append("promote requires positive outcome_quality_delta")
        if quality_delta < MIN_PROMOTION_QUALITY_DELTA:
            failures.append(f"promote requires outcome_quality_delta >= {MIN_PROMOTION_QUALITY_DELTA:.2f}")
        if overhead_ratio > 1.25 and quality_delta < MIN_PROMOTION_QUALITY_DELTA:
            failures.append(f"promote with overhead_ratio > 1.25 requires outcome_quality_delta >= {MIN_PROMOTION_QUALITY_DELTA:.2f}")
        if overhead_ratio > 1.50 and quality_delta < 0.05:
            failures.append("promote with overhead_ratio > 1.50 and quality_delta < 0.05 must stay shadowed")
        if data.get("violations"):
            failures.append("promote requires no violations")
        if not data.get("verification_evidence"):
            failures.append("promote requires verification evidence")
        if has_authority_violation:
            failures.append("promote cannot include authority violation evidence")

    if data.get("status") == "completed":
        if not data.get("verification_evidence"):
            failures.append("completed run requires verification evidence")
        if not data.get("evidence_ledger"):
            failures.append("completed run requires evidence ledger entries")
        evidence_kinds = {evidence.get("kind") for evidence in data.get("evidence_ledger") or [] if isinstance(evidence, dict)}
        if "verification_ref" not in evidence_kinds:
            failures.append("completed run requires verification_ref evidence")
        if data.get("workflow_kind") == "deep_research":
            for required_kind in ("source_ref", "cross_check"):
                if required_kind not in evidence_kinds:
                    failures.append(f"deep_research run requires {required_kind} evidence")
            if metrics.get("unsupported_claim_count", 0) > 0 and "discarded_claim" not in evidence_kinds:
                failures.append("deep_research run with unsupported claims requires discarded_claim evidence")
        if data.get("final_recommendation") == "unknown":
            failures.append("completed run requires a non-unknown final recommendation")
        if comparison.get("recommendation") == "unknown":
            failures.append("completed run requires quality comparison recommendation")
        elif data.get("final_recommendation") != comparison.get("recommendation"):
            failures.append("completed run final_recommendation must match quality_comparison recommendation")
        if comparison.get("baseline_result_ref") == "unrecorded" or comparison.get("candidate_result_ref") == "unrecorded":
            failures.append("completed run requires baseline and candidate result refs")
    if has_authority_violation and not data.get("violations"):
        failures.append("authority violation evidence requires violations entry")
    return failures


def emit_failures(failures: list[str]) -> int:
    for failure in failures:
        print(f"failure: {failure}", file=sys.stderr)
    return 1 if failures else 0


def start(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"workflow run already exists: {path}", file=sys.stderr)
        return 1
    repo_root = resolve_path(args.repo_root)
    if path_contains_or_equals(path, repo_root) and not args.promoted_artifact_ref:
        print("repo-local workflow-run artifacts require --promoted-artifact-ref", file=sys.stderr)
        return 1
    timestamp = now_utc()
    data = {
        "format": RUN_FORMAT,
        "run_id": args.run_id,
        "repo_root": str(repo_root),
        "status": "shadow",
        "workflow_kind": args.workflow_kind,
        "workflow_name": args.workflow_name,
        "mapped_surfaces": args.mapped_surface,
        "backend": args.backend,
        "backend_provenance": backend_provenance_for(args.backend, args.backend_summary, args.command_ref),
        "mode": args.mode,
        "artifact_storage": artifact_storage_for(args.promoted_artifact_ref),
        "source_of_truth_refs": args.source_of_truth_ref,
        "success_criteria": args.success_criterion,
        "forbidden_authority_claims": list(FORBIDDEN_AUTHORITY_TERMS),
        "workers": [],
        "evidence_ledger": [],
        "quality_comparison": quality_comparison(),
        "metrics": metrics_for(),
        "verification_evidence": [],
        "violations": [],
        "final_recommendation": "unknown",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"workflow run started: {path}")
    return 0


def check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    failures = run_failures(load_json(path))
    if failures:
        return emit_failures(failures)
    print(f"workflow run ok: {path}")
    return 0


def add_worker(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    worker = {
        "worker_id": args.worker_id,
        "role": args.role,
        "scope": args.scope,
        "allowed_outputs": args.allowed_output,
        "write_scope": args.write_scope or [],
        "status": args.status,
    }
    data.setdefault("workers", []).append(worker)
    metrics = data.setdefault("metrics", metrics_for())
    metrics["worker_count"] = len(data.get("workers") or [])
    metrics["max_concurrency"] = max(metrics.get("max_concurrency", 0), metrics["worker_count"])
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"worker added: {args.worker_id}")
    return 0


def add_evidence(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    evidence = {
        "evidence_id": args.evidence_id,
        "kind": args.kind,
        "summary": args.summary,
        "refs": args.ref or [],
        "status": args.status,
    }
    data.setdefault("evidence_ledger", []).append(evidence)
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"evidence added: {args.evidence_id}")
    return 0


def record_comparison(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    data["quality_comparison"] = {
        "baseline_result_ref": args.baseline_result_ref,
        "candidate_result_ref": args.candidate_result_ref,
        "acceptance_criteria": args.acceptance_criterion,
        "outcome_quality_delta": args.outcome_quality_delta,
        "overhead_ratio": args.overhead_ratio,
        "recommendation": args.recommendation,
    }
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"comparison recorded: {path}")
    return 0


def record_metrics(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    data["metrics"] = {
        "worker_count": args.worker_count,
        "max_concurrency": args.max_concurrency,
        "unsupported_claim_count": args.unsupported_claim_count,
        "token_or_cost_overhead_ref": args.token_or_cost_overhead_ref,
        "write_scopes_disjoint": args.write_scopes_disjoint,
    }
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"metrics recorded: {path}")
    return 0


def add_violation(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    data.setdefault("violations", []).append(args.violation)
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"violation added: {args.violation}")
    return 0


def complete(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    data["status"] = "completed"
    data["verification_evidence"] = args.verification_evidence
    data["final_recommendation"] = args.final_recommendation
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"workflow run completed: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a Sejong Codex-migrated or mocked workflow run artifact.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a workflow run artifact.")
    start_parser.add_argument("--path", required=True)
    start_parser.add_argument("--run-id", required=True)
    start_parser.add_argument("--repo-root", default=".")
    start_parser.add_argument("--workflow-kind", required=True, choices=sorted(WORKFLOW_KINDS))
    start_parser.add_argument("--workflow-name", required=True)
    start_parser.add_argument("--backend", required=True, choices=sorted(BACKENDS))
    start_parser.add_argument("--backend-summary", help="Explicit backend provenance summary; required for backend=other.")
    start_parser.add_argument("--command-ref", action="append", help="Command or mock provenance ref; required for backend=other.")
    start_parser.add_argument("--promoted-artifact-ref", help="Explicit reason/ref when writing a workflow-run artifact inside the repo.")
    start_parser.add_argument("--mode", default="shadow", choices=sorted(MODES))
    start_parser.add_argument("--mapped-surface", action="append", required=True, choices=sorted(SURFACES))
    start_parser.add_argument("--source-of-truth-ref", action="append", required=True)
    start_parser.add_argument("--success-criterion", action="append", required=True)
    start_parser.add_argument("--force", action="store_true")
    start_parser.set_defaults(func=start)

    check_parser = subparsers.add_parser("check", help="Validate a workflow run artifact.")
    check_parser.add_argument("--path", required=True)
    check_parser.set_defaults(func=check)

    worker_parser = subparsers.add_parser("add-worker", help="Append a bounded worker lane.")
    worker_parser.add_argument("--path", required=True)
    worker_parser.add_argument("--worker-id", required=True)
    worker_parser.add_argument("--role", required=True)
    worker_parser.add_argument("--scope", required=True)
    worker_parser.add_argument("--allowed-output", action="append", required=True)
    worker_parser.add_argument("--write-scope", action="append")
    worker_parser.add_argument("--status", default="completed", choices=sorted(WORKER_STATUSES))
    worker_parser.set_defaults(func=add_worker)

    evidence_parser = subparsers.add_parser("add-evidence", help="Append a workflow evidence ledger entry.")
    evidence_parser.add_argument("--path", required=True)
    evidence_parser.add_argument("--evidence-id", required=True)
    evidence_parser.add_argument("--kind", required=True, choices=sorted(EVIDENCE_KINDS))
    evidence_parser.add_argument("--summary", required=True)
    evidence_parser.add_argument("--ref", action="append")
    evidence_parser.add_argument("--status", required=True, choices=sorted(EVIDENCE_STATUSES))
    evidence_parser.set_defaults(func=add_evidence)

    comparison_parser = subparsers.add_parser("record-comparison", help="Record baseline-vs-candidate quality comparison.")
    comparison_parser.add_argument("--path", required=True)
    comparison_parser.add_argument("--baseline-result-ref", required=True)
    comparison_parser.add_argument("--candidate-result-ref", required=True)
    comparison_parser.add_argument("--acceptance-criterion", action="append", required=True)
    comparison_parser.add_argument("--outcome-quality-delta", required=True, type=float)
    comparison_parser.add_argument("--overhead-ratio", required=True, type=float)
    comparison_parser.add_argument("--recommendation", required=True, choices=sorted(RECOMMENDATIONS))
    comparison_parser.set_defaults(func=record_comparison)

    metrics_parser = subparsers.add_parser("record-metrics", help="Record worker, concurrency, claim, and overhead metrics.")
    metrics_parser.add_argument("--path", required=True)
    metrics_parser.add_argument("--worker-count", required=True, type=int)
    metrics_parser.add_argument("--max-concurrency", required=True, type=int)
    metrics_parser.add_argument("--unsupported-claim-count", required=True, type=int)
    metrics_parser.add_argument("--token-or-cost-overhead-ref", required=True)
    metrics_parser.add_argument("--write-scopes-disjoint", action=argparse.BooleanOptionalAction, default=True)
    metrics_parser.set_defaults(func=record_metrics)

    violation_parser = subparsers.add_parser("add-violation", help="Record a workflow authority or safety violation.")
    violation_parser.add_argument("--path", required=True)
    violation_parser.add_argument("--violation", required=True)
    violation_parser.set_defaults(func=add_violation)

    complete_parser = subparsers.add_parser("complete", help="Complete the workflow run with a final recommendation.")
    complete_parser.add_argument("--path", required=True)
    complete_parser.add_argument("--verification-evidence", action="append", required=True)
    complete_parser.add_argument("--final-recommendation", required=True, choices=sorted(RECOMMENDATIONS))
    complete_parser.set_defaults(func=complete)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
