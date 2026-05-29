#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sejong_workflow_run import RUN_FORMAT, path_contains_or_equals, run_failures


SYMBOLIC_REF_PREFIXES = (
    "baseline:",
    "candidate:",
    "benchmark:",
    "mock:",
    "worker:",
    "manual-shadow:",
    "artifact:",
)
COMMAND_REF_PREFIXES = (
    "python ",
    "python3 ",
    "bash ",
    "uv ",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def local_ref_candidates(ref: str, repo_root: Path, artifact_path: Path) -> list[Path]:
    if ref.startswith(SYMBOLIC_REF_PREFIXES) or ref.startswith(COMMAND_REF_PREFIXES):
        return []
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        return []
    if parsed.scheme and len(parsed.scheme) > 1:
        return []
    path = Path(ref)
    if path.is_absolute():
        return [path]
    return [repo_root / path, artifact_path.parent / path]


def ref_kind(ref: str, repo_root: Path, artifact_path: Path) -> str:
    if not isinstance(ref, str) or not ref:
        return "invalid"
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        return "url"
    if ref.startswith(COMMAND_REF_PREFIXES):
        return "command"
    if ref.startswith(SYMBOLIC_REF_PREFIXES):
        return "symbolic"
    candidates = local_ref_candidates(ref, repo_root, artifact_path)
    if candidates and any(candidate.exists() for candidate in candidates):
        return "local_existing"
    if "/" in ref or "." in ref:
        return "local_missing"
    return "symbolic"


def audit_artifact(path: Path, repo_root: Path, strict_local_refs: bool) -> dict[str, Any]:
    data = load_json(path)
    failures = run_failures(data)
    warnings: list[str] = []

    if data.get("format") != RUN_FORMAT:
        failures.append(f"unexpected workflow-run format: {data.get('format')}")

    artifact_storage = data.get("artifact_storage") if isinstance(data.get("artifact_storage"), dict) else {}
    if path_contains_or_equals(path.resolve(), repo_root.resolve()) and artifact_storage.get("scope") not in {
        "promoted_example",
        "promoted_repo_artifact",
    }:
        failures.append("repo-local workflow-run artifact requires promoted artifact storage scope")

    comparison = data.get("quality_comparison") if isinstance(data.get("quality_comparison"), dict) else {}
    baseline_ref = comparison.get("baseline_result_ref")
    candidate_ref = comparison.get("candidate_result_ref")
    ref_audits = []
    for label, ref in (("baseline_result_ref", baseline_ref), ("candidate_result_ref", candidate_ref)):
        kind = ref_kind(ref, repo_root, path) if isinstance(ref, str) else "invalid"
        ref_audits.append({"field": label, "ref": ref, "kind": kind})
        if strict_local_refs and kind not in {"local_existing", "url"}:
            failures.append(f"{label} must resolve to an existing local file or URL in strict evidence mode")
        elif kind == "symbolic":
            warnings.append(f"{label} is symbolic; strict evidence mode is required for promotion proof")
        elif kind == "local_missing":
            failures.append(f"{label} points to a missing local file")

    evidence_ref_counts = {"local_existing": 0, "local_missing": 0, "url": 0, "command": 0, "symbolic": 0, "invalid": 0}
    for evidence in data.get("evidence_ledger") or []:
        if not isinstance(evidence, dict):
            continue
        for ref in evidence.get("refs") or []:
            kind = ref_kind(ref, repo_root, path)
            evidence_ref_counts[kind] = evidence_ref_counts.get(kind, 0) + 1
            if kind == "local_missing":
                failures.append(f"evidence {evidence.get('evidence_id') or '<missing>'} ref points to a missing local file: {ref}")

    return {
        "path": str(path),
        "run_id": data.get("run_id"),
        "workflow_kind": data.get("workflow_kind"),
        "backend": data.get("backend"),
        "final_recommendation": data.get("final_recommendation"),
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "quality_ref_audit": ref_audits,
        "evidence_ref_counts": evidence_ref_counts,
    }


def discover_artifacts(paths: list[str], dirs: list[str]) -> list[Path]:
    artifacts = [Path(path) for path in paths]
    for directory in dirs:
        root = Path(directory)
        artifacts.extend(path for path in sorted(root.rglob("*.json")) if path.is_file())
    return sorted(set(artifacts))


def audit_corpus(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    artifacts = discover_artifacts(args.artifact, args.artifact_dir)
    results = [
        audit_artifact(path.resolve(), repo_root, args.strict_local_refs)
        for path in artifacts
        if path.exists()
    ]
    missing = [path for path in artifacts if not path.exists()]
    failures = [f"missing artifact path: {path}" for path in missing]
    failures.extend(f"{result['path']}: {failure}" for result in results for failure in result["failures"])

    workflow_kinds = {result["workflow_kind"] for result in results if result["workflow_kind"]}
    backends = {result["backend"] for result in results if result["backend"]}
    recommendations = {result["final_recommendation"] for result in results if result["final_recommendation"]}
    promoted_count = sum(1 for result in results if result["final_recommendation"] == "promote")
    if len(results) < args.min_artifacts:
        failures.append(f"artifact corpus has {len(results)} artifacts; expected at least {args.min_artifacts}")
    if len(workflow_kinds) < args.min_workflow_kinds:
        failures.append(f"artifact corpus has {len(workflow_kinds)} workflow kinds; expected at least {args.min_workflow_kinds}")
    if len(backends) < args.min_backends:
        failures.append(f"artifact corpus has {len(backends)} backends; expected at least {args.min_backends}")
    if args.require_promoted and promoted_count == 0:
        failures.append("artifact corpus requires at least one promoted run")

    return {
        "format": "sejong.workflow-run-risk-audit/v0.1-draft",
        "passed": not failures,
        "repo_root": str(repo_root),
        "artifact_count": len(results),
        "workflow_kind_count": len(workflow_kinds),
        "backend_count": len(backends),
        "recommendations": sorted(recommendations),
        "promoted_count": promoted_count,
        "strict_local_refs": args.strict_local_refs,
        "min_artifacts": args.min_artifacts,
        "min_workflow_kinds": args.min_workflow_kinds,
        "min_backends": args.min_backends,
        "require_promoted": args.require_promoted,
        "failures": failures,
        "artifacts": results,
        "notes": [
            "This audit verifies evidence/provenance hygiene for workflow-run artifacts.",
            "Use --strict-local-refs for promotion proof so baseline/candidate refs resolve to existing files or URLs.",
            "It does not execute the referenced commands or independently judge task quality.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit workflow-run artifacts for remaining promotion-risk evidence gaps.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--artifact-dir", action="append", default=[])
    parser.add_argument("--min-artifacts", type=int, default=1)
    parser.add_argument("--min-workflow-kinds", type=int, default=1)
    parser.add_argument("--min-backends", type=int, default=1)
    parser.add_argument("--require-promoted", action="store_true")
    parser.add_argument("--strict-local-refs", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = audit_corpus(args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "workflow_run_risk_audit "
            f"{'ok' if payload['passed'] else 'failed'}: "
            f"artifacts={payload['artifact_count']} kinds={payload['workflow_kind_count']} "
            f"backends={payload['backend_count']} promoted={payload['promoted_count']}"
        )
        if not payload["passed"]:
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
