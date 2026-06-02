#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import resolve_path


FORMAT = "sejong.continuity-capsule/v0.1-draft"
SURFACES = {
    "sejong",
    "jangyeongsil",
    "jiphyeonjeon",
    "uigwe",
    "seungjeongwon",
    "sillok",
    "danjong",
    "sejong-direct",
}
PROJECTION_PROFILES = {"micro", "standard", "frontier", "retrieval"}
REQUIRED_FIELDS = (
    "format",
    "capsule_id",
    "active_context_id",
    "repo_root",
    "run_id",
    "objective",
    "task_class",
    "current_surface",
    "route_sequence",
    "pending_gates",
    "projection_profile",
    "source_artifact_refs",
    "evidence_refs",
    "selected_decisions",
    "rejected_options",
    "active_blockers",
    "verification_state",
    "next_action",
    "do_not_do",
    "stale_triggers",
    "risk_flags",
    "last_updated_at",
)
STRING_LIST_FIELDS = (
    "route_sequence",
    "pending_gates",
    "source_artifact_refs",
    "evidence_refs",
    "active_blockers",
    "do_not_do",
    "stale_triggers",
    "risk_flags",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unique_append(values: list[str], additions: list[str] | None) -> list[str]:
    result = list(values)
    for item in additions or []:
        if item and item not in result:
            result.append(item)
    return result


def string_list_failures(data: dict[str, Any], field: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must contain only non-empty strings"]
    return []


def decision_failures(data: dict[str, Any], field: str, required_text_field: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    failures: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            failures.append(f"{field}[{index}] must be an object")
            continue
        for required in ("id", "summary", required_text_field, "refs"):
            if required not in item:
                failures.append(f"{field}[{index}] missing {required}")
        refs = item.get("refs")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            failures.append(f"{field}[{index}].refs must contain only non-empty strings")
    return failures


def upsert_record(items: list[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    replaced = False
    for item in items:
        if item.get("id") == record["id"]:
            result.append(record)
            replaced = True
        else:
            result.append(item)
    if not replaced:
        result.append(record)
    return result


def capsule_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            failures.append(f"missing {field}")
    if data.get("format") != FORMAT:
        failures.append(f"unexpected format: {data.get('format')}")
    if data.get("current_surface") not in SURFACES:
        failures.append(f"invalid current_surface: {data.get('current_surface')}")
    if data.get("projection_profile") not in PROJECTION_PROFILES:
        failures.append(f"invalid projection_profile: {data.get('projection_profile')}")
    for field in STRING_LIST_FIELDS:
        if field in data:
            failures.extend(string_list_failures(data, field))
    failures.extend(decision_failures(data, "selected_decisions", "why"))
    failures.extend(decision_failures(data, "rejected_options", "reason"))
    verification = data.get("verification_state")
    if not isinstance(verification, dict):
        failures.append("verification_state must be an object")
    else:
        status = verification.get("status")
        if status not in {"unverified", "in_progress", "passed", "failed", "blocked"}:
            failures.append(f"invalid verification_state.status: {status}")
        for field in ("last_verified_claim", "refs"):
            if field not in verification:
                failures.append(f"verification_state missing {field}")
        refs = verification.get("refs")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            failures.append("verification_state.refs must contain only non-empty strings")
    return failures


def short_join(items: list[str], *, limit: int = 3) -> str:
    if not items:
        return "none"
    clipped = items[:limit]
    suffix = f",+{len(items) - limit}" if len(items) > limit else ""
    return ",".join(clipped) + suffix


def first_summary(items: list[dict[str, Any]], *, field: str = "summary") -> str:
    if not items:
        return "none"
    value = items[0].get(field) or "none"
    return str(value).replace("\n", " ")


def capsule_projection(data: dict[str, Any], profile: str | None = None) -> str:
    chosen_profile = profile or data.get("projection_profile") or "standard"
    if chosen_profile not in PROJECTION_PROFILES:
        chosen_profile = "standard"
    verification = data.get("verification_state") or {}
    parts = [
        "continuity_capsule="
        f"{data.get('capsule_id')}; profile={chosen_profile}; task_class={data.get('task_class')}; "
        f"surface={data.get('current_surface')}; pending_gates={short_join(data.get('pending_gates') or [])}; "
        f"next_action={data.get('next_action')}; blockers={short_join(data.get('active_blockers') or [])}."
    ]
    if chosen_profile in {"standard", "frontier"}:
        parts.append(
            " continuity_decision="
            f"{first_summary(data.get('selected_decisions') or [])}; "
            f"verification={verification.get('status') or 'unknown'}:{verification.get('last_verified_claim') or 'none'}; "
            f"source_refs={short_join(data.get('source_artifact_refs') or [])}."
        )
    if chosen_profile == "frontier":
        parts.append(
            " continuity_rejected="
            f"{first_summary(data.get('rejected_options') or [])}; "
            f"stale_triggers={short_join(data.get('stale_triggers') or [])}; "
            f"do_not_do={short_join(data.get('do_not_do') or [])}."
        )
    if chosen_profile == "retrieval":
        parts.append(
            " continuity_retrieval_refs="
            f"{short_join((data.get('source_artifact_refs') or []) + (data.get('evidence_refs') or []), limit=6)}."
        )
    return " ".join(parts)


def emit_failures(failures: list[str]) -> int:
    for failure in failures:
        print(f"failure: {failure}")
    return 1 if failures else 0


def check(args: argparse.Namespace) -> int:
    data = load_json(Path(args.path))
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    print(f"continuity capsule ok: {Path(args.path)}")
    return 0


def project(args: argparse.Namespace) -> int:
    data = load_json(Path(args.path))
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    print(capsule_projection(data, args.profile))
    return 0


def update(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    if args.current_surface:
        data["current_surface"] = args.current_surface
    if args.route:
        data["route_sequence"] = unique_append(data.get("route_sequence", []), args.route)
    if args.pending_gate:
        data["pending_gates"] = unique_append(data.get("pending_gates", []), args.pending_gate)
    if args.clear_pending_gate:
        clear = set(args.clear_pending_gate)
        data["pending_gates"] = [gate for gate in data.get("pending_gates", []) if gate not in clear]
    if args.source_artifact_ref:
        data["source_artifact_refs"] = unique_append(data.get("source_artifact_refs", []), args.source_artifact_ref)
    if args.evidence_ref:
        data["evidence_refs"] = unique_append(data.get("evidence_refs", []), args.evidence_ref)
    if args.clear_active_blockers:
        data["active_blockers"] = []
    if args.active_blocker:
        data["active_blockers"] = unique_append(data.get("active_blockers", []), args.active_blocker)
    if args.next_action:
        data["next_action"] = args.next_action
    if args.projection_profile:
        data["projection_profile"] = args.projection_profile
    if args.risk_flag:
        data["risk_flags"] = unique_append(data.get("risk_flags", []), args.risk_flag)
    if args.stale_trigger:
        data["stale_triggers"] = unique_append(data.get("stale_triggers", []), args.stale_trigger)
    verification = dict(data.get("verification_state") or {})
    if args.verification_status:
        verification["status"] = args.verification_status
    if args.last_verified_claim:
        verification["last_verified_claim"] = args.last_verified_claim
    if args.verification_ref:
        verification["refs"] = unique_append(verification.get("refs", []), args.verification_ref)
    data["verification_state"] = verification
    data["last_updated_at"] = now_utc()
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"continuity capsule updated: {path}")
    return 0


def record_decision(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    record = {
        "id": args.decision_id,
        "summary": args.summary,
        "why": args.why,
        "refs": args.ref or [],
    }
    data["selected_decisions"] = upsert_record(data.get("selected_decisions", []), record)
    data["last_updated_at"] = now_utc()
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"decision recorded: {args.decision_id}")
    return 0


def record_rejection(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    record = {
        "id": args.option_id,
        "summary": args.summary,
        "reason": args.reason,
        "refs": args.ref or [],
    }
    data["rejected_options"] = upsert_record(data.get("rejected_options", []), record)
    data["last_updated_at"] = now_utc()
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"rejection recorded: {args.option_id}")
    return 0


def start(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"continuity capsule already exists: {path}")
        return 1
    data = {
        "format": FORMAT,
        "capsule_id": args.capsule_id,
        "active_context_id": args.active_context_id,
        "repo_root": str(resolve_path(args.repo_root)),
        "run_id": args.run_id,
        "objective": args.objective,
        "task_class": args.task_class,
        "current_surface": args.current_surface,
        "route_sequence": args.route or [args.current_surface],
        "pending_gates": args.pending_gate or [],
        "projection_profile": args.projection_profile,
        "source_artifact_refs": args.source_artifact_ref or [],
        "evidence_refs": args.evidence_ref or [],
        "selected_decisions": [],
        "rejected_options": [],
        "active_blockers": args.active_blocker or [],
        "verification_state": {
            "status": args.verification_status,
            "last_verified_claim": args.last_verified_claim,
            "refs": args.verification_ref or [],
        },
        "next_action": args.next_action,
        "do_not_do": args.do_not_do or [],
        "stale_triggers": args.stale_trigger or [],
        "risk_flags": args.risk_flag or [],
        "last_updated_at": now_utc(),
    }
    failures = capsule_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"continuity capsule started: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage King Sejong continuity capsule artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a continuity capsule artifact.")
    start_parser.add_argument("--path", required=True)
    start_parser.add_argument("--capsule-id", required=True)
    start_parser.add_argument("--active-context-id", required=True)
    start_parser.add_argument("--repo-root", default=".")
    start_parser.add_argument("--run-id", required=True)
    start_parser.add_argument("--objective", required=True)
    start_parser.add_argument("--task-class", required=True)
    start_parser.add_argument("--current-surface", choices=sorted(SURFACES), required=True)
    start_parser.add_argument("--route", action="append")
    start_parser.add_argument("--pending-gate", action="append")
    start_parser.add_argument("--projection-profile", choices=sorted(PROJECTION_PROFILES), default="standard")
    start_parser.add_argument("--source-artifact-ref", action="append")
    start_parser.add_argument("--evidence-ref", action="append")
    start_parser.add_argument("--active-blocker", action="append")
    start_parser.add_argument("--verification-status", default="unverified")
    start_parser.add_argument("--last-verified-claim", default="No fresh verification has been recorded.")
    start_parser.add_argument("--verification-ref", action="append")
    start_parser.add_argument("--next-action", required=True)
    start_parser.add_argument("--do-not-do", action="append")
    start_parser.add_argument("--stale-trigger", action="append")
    start_parser.add_argument("--risk-flag", action="append")
    start_parser.add_argument("--force", action="store_true")
    start_parser.set_defaults(func=start)

    check_parser = subparsers.add_parser("check", help="Validate a continuity capsule artifact.")
    check_parser.add_argument("--path", required=True)
    check_parser.set_defaults(func=check)

    project_parser = subparsers.add_parser("project", help="Print a compact model-visible projection.")
    project_parser.add_argument("--path", required=True)
    project_parser.add_argument("--profile", choices=sorted(PROJECTION_PROFILES))
    project_parser.set_defaults(func=project)

    update_parser = subparsers.add_parser("update", help="Update runtime fields on a continuity capsule.")
    update_parser.add_argument("--path", required=True)
    update_parser.add_argument("--current-surface", choices=sorted(SURFACES))
    update_parser.add_argument("--route", action="append")
    update_parser.add_argument("--pending-gate", action="append")
    update_parser.add_argument("--clear-pending-gate", action="append")
    update_parser.add_argument("--projection-profile", choices=sorted(PROJECTION_PROFILES))
    update_parser.add_argument("--source-artifact-ref", action="append")
    update_parser.add_argument("--evidence-ref", action="append")
    update_parser.add_argument("--active-blocker", action="append")
    update_parser.add_argument("--clear-active-blockers", action="store_true")
    update_parser.add_argument("--next-action")
    update_parser.add_argument("--verification-status")
    update_parser.add_argument("--last-verified-claim")
    update_parser.add_argument("--verification-ref", action="append")
    update_parser.add_argument("--risk-flag", action="append")
    update_parser.add_argument("--stale-trigger", action="append")
    update_parser.set_defaults(func=update)

    decision_parser = subparsers.add_parser("record-decision", help="Upsert a selected decision into a capsule.")
    decision_parser.add_argument("--path", required=True)
    decision_parser.add_argument("--decision-id", required=True)
    decision_parser.add_argument("--summary", required=True)
    decision_parser.add_argument("--why", required=True)
    decision_parser.add_argument("--ref", action="append")
    decision_parser.set_defaults(func=record_decision)

    rejection_parser = subparsers.add_parser("record-rejection", help="Upsert a rejected option into a capsule.")
    rejection_parser.add_argument("--path", required=True)
    rejection_parser.add_argument("--option-id", required=True)
    rejection_parser.add_argument("--summary", required=True)
    rejection_parser.add_argument("--reason", required=True)
    rejection_parser.add_argument("--ref", action="append")
    rejection_parser.set_defaults(func=record_rejection)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
