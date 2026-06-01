#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import path_contains_or_equals, path_key, resolve_path


FORMAT = "king-sejong.context/v0.1-draft"
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
REQUIRED_FIELDS = (
    "format",
    "active_context_id",
    "repo_id",
    "repo_root",
    "run_id",
    "session_id",
    "route_id",
    "current_surface",
    "route_sequence",
    "required_route_sequence",
    "last_user_intent",
    "pending_gates",
    "protected_paths",
    "allowed_direct_change_types",
    "evidence_refs",
    "artifact_refs",
    "team_run_refs",
    "subagent_refs",
    "exit_conditions",
    "last_updated_at",
)
LIST_FIELDS = (
    "route_sequence",
    "required_route_sequence",
    "pending_gates",
    "protected_paths",
    "allowed_direct_change_types",
    "evidence_refs",
    "artifact_refs",
    "team_run_refs",
    "subagent_refs",
    "exit_conditions",
)
DEFAULT_DIRECT_CHANGE_TYPES = (
    "typo",
    "broken_link",
    "formatting_only",
    "deterministic_scorecard_regeneration",
)
DEFAULT_EXIT_CONDITIONS = (
    "user_explicitly_exits_sejong",
    "user_switches_to_non_sejong_workflow",
    "host_conversation_ends",
)
SEUNGJEONGWON_RECEIPT_GATE = "seungjeongwon_receipt_required"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sejong_root() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def active_context_path() -> Path:
    if os.environ.get("SEJONG_ACTIVE_CONTEXT"):
        return Path(os.environ["SEJONG_ACTIVE_CONTEXT"]).expanduser()
    return sejong_root() / "state" / "active-context.json"


def repo_slug(repo_root: Path) -> str:
    repo_root = resolve_path(repo_root)
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in repo_root.name).strip("-")
    digest = hashlib.sha1(path_key(repo_root).encode("utf-8")).hexdigest()[:8]
    return f"{safe_name or 'repo'}-{digest}"


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def unique_append(values: list[str], additions: list[str]) -> list[str]:
    result = list(values)
    for item in additions:
        if item and item not in result:
            result.append(item)
    return result


def add_goal_bearing_execution_defaults(
    required_route_sequence: list[str],
    pending_gates: list[str],
    *,
    goal_bearing: bool,
) -> tuple[list[str], list[str]]:
    required = list(required_route_sequence)
    pending = list(pending_gates)
    if goal_bearing:
        required = unique_append(required, ["uigwe", "seungjeongwon"])
    if "seungjeongwon" in required:
        pending = unique_append(pending, [SEUNGJEONGWON_RECEIPT_GATE])
    return required, pending


def coerce_ref_item(item: Any) -> str | None:
    if isinstance(item, str):
        return item or None
    if isinstance(item, dict):
        for key in ("ref", "path", "id", "run_id", "active_context_id", "summary"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    if item is None:
        return None
    compact = json.dumps(item, sort_keys=True, separators=(",", ":"))
    return compact if compact else None


def coerce_string_list(value: Any) -> list[str]:
    raw_items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in raw_items:
        coerced = coerce_ref_item(item)
        if coerced and coerced not in result:
            result.append(coerced)
    return result


def normalize_context_string_lists(context: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(context)
    for field in LIST_FIELDS:
        if field in normalized:
            normalized[field] = coerce_string_list(normalized[field])
    return normalized


def validate_context(context: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in context:
            failures.append(f"missing {field}")
    if context.get("format") != FORMAT:
        failures.append("unexpected format")
    if context.get("current_surface") not in SURFACES:
        failures.append(f"invalid current_surface: {context.get('current_surface')}")
    for field in LIST_FIELDS:
        if field in context and not isinstance(context[field], list):
            failures.append(f"{field} must be a list")
        elif field in context:
            invalid_items = [item for item in context[field] if not isinstance(item, str) or not item]
            if invalid_items:
                failures.append(f"{field} must contain only non-empty strings")
    return failures


def context_run_path(context: dict[str, Any]) -> Path:
    run_id = context["run_id"]
    repo_id = context["repo_id"]
    return sejong_root() / "runs" / repo_id / run_id / "king-sejong-context.json"


def save_context(context: dict[str, Any], *, update_active: bool = True) -> Path:
    context["last_updated_at"] = now_utc()
    run_path = context_run_path(context)
    write_json(run_path, context)
    if update_active:
        write_json(active_context_path(), context)
    return run_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage King Sejong active context checkpoints.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a new active King Sejong context.")
    start.add_argument("--repo-root", default=".")
    start.add_argument("--repo-id")
    start.add_argument("--run-id")
    start.add_argument("--session-id")
    start.add_argument("--route-id")
    start.add_argument("--current-surface", default="sejong", choices=sorted(SURFACES))
    start.add_argument("--route", action="append", dest="route_sequence")
    start.add_argument("--required-route", action="append", dest="required_route_sequence")
    start.add_argument("--pending-gate", action="append", dest="pending_gates")
    start.add_argument(
        "--goal-bearing",
        action="store_true",
        help="Mark an outcome-completion workflow; adds Uigwe -> Seungjeongwon and the receipt gate.",
    )
    start.add_argument("--protected-path", action="append", dest="protected_paths")
    start.add_argument("--allowed-direct-change-type", action="append", dest="allowed_direct_change_types")
    start.add_argument("--last-user-intent", default="King Sejong workflow started.")
    start.set_defaults(func=start_context)

    update = subparsers.add_parser("update", help="Update the active King Sejong context.")
    update.add_argument("--context")
    update.add_argument("--current-surface", choices=sorted(SURFACES))
    update.add_argument("--append-route", action="append", dest="append_routes")
    update.add_argument("--set-route-sequence", action="append", dest="set_route_sequence")
    update.add_argument("--add-required-route", action="append", dest="add_required_routes")
    update.add_argument("--add-pending-gate", action="append", dest="add_pending_gates")
    update.add_argument(
        "--require-seungjeongwon-receipt",
        action="store_true",
        help="Require a Seungjeongwon execution receipt before write-like execution.",
    )
    update.add_argument("--clear-pending-gate", action="append", dest="clear_pending_gates")
    update.add_argument("--add-protected-path", action="append", dest="add_protected_paths")
    update.add_argument("--add-evidence-ref", action="append", dest="add_evidence_refs")
    update.add_argument("--add-artifact-ref", action="append", dest="add_artifact_refs")
    update.add_argument("--add-team-run-ref", action="append", dest="add_team_run_refs")
    update.add_argument("--add-subagent-ref", action="append", dest="add_subagent_refs")
    update.add_argument("--last-user-intent")
    update.set_defaults(func=update_context)

    doctor = subparsers.add_parser("doctor", help="Validate the active King Sejong context.")
    doctor.add_argument("--context")
    doctor.add_argument("--repo-root")
    doctor.set_defaults(func=doctor_context)

    repair = subparsers.add_parser("repair", help="Repair simple active-context shape drift.")
    repair.add_argument("--context")
    repair.set_defaults(func=repair_context)

    close = subparsers.add_parser("close", help="Archive and remove the active context pointer.")
    close.add_argument("--context")
    close.set_defaults(func=close_context)

    return parser


def start_context(args: argparse.Namespace) -> int:
    repo_root = resolve_path(args.repo_root)
    run_id = args.run_id or default_run_id()
    repo_id = args.repo_id or repo_slug(repo_root)
    route_sequence = args.route_sequence or [args.current_surface]
    required_route_sequence, pending_gates = add_goal_bearing_execution_defaults(
        args.required_route_sequence or [],
        args.pending_gates or [],
        goal_bearing=args.goal_bearing,
    )
    context = {
        "format": FORMAT,
        "active_context_id": f"ctx-{run_id}",
        "repo_id": repo_id,
        "repo_root": str(repo_root),
        "run_id": run_id,
        "session_id": args.session_id or f"session-{run_id}",
        "route_id": args.route_id or f"route-{run_id}",
        "current_surface": args.current_surface,
        "route_sequence": route_sequence,
        "required_route_sequence": required_route_sequence,
        "last_user_intent": args.last_user_intent,
        "pending_gates": pending_gates,
        "protected_paths": args.protected_paths or [],
        "allowed_direct_change_types": args.allowed_direct_change_types or list(DEFAULT_DIRECT_CHANGE_TYPES),
        "evidence_refs": [],
        "artifact_refs": [],
        "team_run_refs": [],
        "subagent_refs": [],
        "exit_conditions": list(DEFAULT_EXIT_CONDITIONS),
        "last_updated_at": now_utc(),
    }
    failures = validate_context(context)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    run_path = save_context(context)
    print(f"active_context={active_context_path()}")
    print(f"run_context={run_path}")
    return 0


def load_context_argument(path: str | None) -> tuple[Path, dict[str, Any]]:
    context_path = Path(path).expanduser() if path else active_context_path()
    if not context_path.exists():
        raise SystemExit(f"active context does not exist: {context_path}")
    return context_path, load_json(context_path)


def update_context(args: argparse.Namespace) -> int:
    _, context = load_context_argument(args.context)
    if args.current_surface:
        context["current_surface"] = args.current_surface
    if args.set_route_sequence:
        context["route_sequence"] = args.set_route_sequence
    if args.append_routes:
        context["route_sequence"] = unique_append(context.get("route_sequence", []), args.append_routes)
    if args.add_required_routes:
        context["required_route_sequence"] = unique_append(
            context.get("required_route_sequence", []), args.add_required_routes
        )
    if args.add_pending_gates:
        context["pending_gates"] = unique_append(context.get("pending_gates", []), args.add_pending_gates)
    if args.require_seungjeongwon_receipt:
        context["required_route_sequence"] = unique_append(
            context.get("required_route_sequence", []), ["seungjeongwon"]
        )
        context["pending_gates"] = unique_append(
            context.get("pending_gates", []), [SEUNGJEONGWON_RECEIPT_GATE]
        )
    if args.clear_pending_gates:
        clear = set(args.clear_pending_gates)
        context["pending_gates"] = [gate for gate in context.get("pending_gates", []) if gate not in clear]
    if args.add_protected_paths:
        context["protected_paths"] = unique_append(context.get("protected_paths", []), args.add_protected_paths)
    if args.add_evidence_refs:
        context["evidence_refs"] = unique_append(context.get("evidence_refs", []), args.add_evidence_refs)
    if args.add_artifact_refs:
        context["artifact_refs"] = unique_append(context.get("artifact_refs", []), args.add_artifact_refs)
    if args.add_team_run_refs:
        context["team_run_refs"] = unique_append(context.get("team_run_refs", []), args.add_team_run_refs)
    if args.add_subagent_refs:
        context["subagent_refs"] = unique_append(context.get("subagent_refs", []), args.add_subagent_refs)
    if args.last_user_intent:
        context["last_user_intent"] = args.last_user_intent

    failures = validate_context(context)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    run_path = save_context(context)
    print(f"context updated: {run_path}")
    return 0


def doctor_context(args: argparse.Namespace) -> int:
    context_path, context = load_context_argument(args.context)
    failures = validate_context(context)
    if args.repo_root:
        repo_root = resolve_path(args.repo_root)
        context_root = resolve_path(context.get("repo_root", ""))
        if not path_contains_or_equals(repo_root, context_root):
            failures.append(
                "context repo_root does not cover requested repo: "
                f"{repo_root}; context_repo_root={context_root}"
            )
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        if any("must contain only non-empty strings" in failure or "must be a list" in failure for failure in failures):
            print(
                f"repair suggestion: python3 {Path(__file__).name} repair --context {context_path}",
                file=sys.stderr,
            )
        return 1
    print(f"context ok: {context_path}")
    print(f"active_context_id={context['active_context_id']}")
    print(f"current_surface={context['current_surface']}")
    print(f"pending_gates={','.join(context['pending_gates']) or 'none'}")
    return 0


def repair_context(args: argparse.Namespace) -> int:
    _, context = load_context_argument(args.context)
    repaired = normalize_context_string_lists(context)
    failures = validate_context(repaired)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    run_path = save_context(repaired)
    print(f"context repaired: {run_path}")
    return 0


def close_context(args: argparse.Namespace) -> int:
    context_path, context = load_context_argument(args.context)
    save_context(context, update_active=False)
    if context_path == active_context_path() and context_path.exists():
        context_path.unlink()
    print(f"context closed: {context['active_context_id']}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
