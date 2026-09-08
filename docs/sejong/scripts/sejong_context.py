#!/usr/bin/env python3
# noqa: SIZE_OK -- active-context CLI remains single-file for Phase 1 compatibility
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import declared_repo_identity, identity_path_digest, repo_identity, resolve_path
from sejong_runtime_lock import (
    RuntimeLock,
    RuntimeLockClass,
    RuntimeLockReleaseError,
    RuntimeLockRequest,
    RuntimeLockTimeout,
    acquire_runtime_lock,
)
from sejong_session_binding import (
    BindingRevisionConflict,
    DERIVED_STATE_WARNINGS_FIELD,
    InvalidBinding,
    StaleBindingObservation,
    atomic_write_json,
    bind_context,
    load_binding,
    migrate_legacy_pointer,
    observe_binding,
    resolve_bound_context,
    unbind_session,
    update_repo_index,
)


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
PROJECTION_PROFILES = {"micro", "standard", "frontier", "retrieval"}
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
REQUIRED_STRING_FIELDS = (
    "active_context_id",
    "repo_id",
    "repo_root",
    "run_id",
    "session_id",
    "route_id",
    "last_user_intent",
    "last_updated_at",
)
LIST_FIELDS = (
    "repo_identities",
    "route_sequence",
    "required_route_sequence",
    "pending_gates",
    "protected_paths",
    "allowed_direct_change_types",
    "objective_refs",
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
UIGWE_PROMOTION_GATE = "uigwe_promotion_required"
CONTEXT_LOCK_TIMEOUT_ENV = "SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS"
DEFAULT_CONTEXT_LOCK_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class InvalidContextLockTimeout(Exception):
    raw_value: str

    def __str__(self) -> str:
        return (
            f"invalid {CONTEXT_LOCK_TIMEOUT_ENV}={self.raw_value!r}; "
            "expected a finite positive number of seconds"
        )


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sejong_root() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def repo_slug(repo_root: Path) -> str:
    repo_root = resolve_path(repo_root)
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in repo_root.name).strip("-")
    digest = identity_path_digest(repo_root)[:8]
    return f"{safe_name or 'repo'}-{digest}"


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_json(path, data)


def context_lock_timeout_seconds() -> float:
    configured = os.environ.get(CONTEXT_LOCK_TIMEOUT_ENV)
    if configured is None:
        return DEFAULT_CONTEXT_LOCK_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(configured)
    except ValueError as error:
        raise InvalidContextLockTimeout(configured) from error
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
        raise InvalidContextLockTimeout(configured)
    return timeout_seconds


def device_id() -> str:
    configured = os.environ.get("SEJONG_DEVICE_ID")
    if configured:
        return configured
    return socket.gethostname() or "local-device"


def context_identity_value(context: dict[str, Any], field: str, fallback: str) -> str:
    value = context.get(field)
    return value if isinstance(value, str) and value else fallback


def run_context_lock_name(context: dict[str, Any]) -> str:
    repo_id = context_identity_value(context, "repo_id", "unknown-repo")
    run_id = context_identity_value(context, "run_id", "unknown-run")
    digest = hashlib.sha1(f"{repo_id}:{run_id}".encode("utf-8")).hexdigest()[:16]
    return f"run-context-{digest}"


def acquire_run_context_lock(
    context: dict[str, Any],
    operation: str,
    *,
    sejong_home: Path | None = None,
) -> RuntimeLock:
    return acquire_runtime_lock(
        RuntimeLockRequest(
            sejong_home=sejong_home or sejong_root(),
            lock_name=run_context_lock_name(context),
            lock_class=RuntimeLockClass.RUN_CONTEXT,
            owner_session_id=context_identity_value(context, "session_id", "unknown-session"),
            owner_device_id=device_id(),
            operation=operation,
            owner_run_id=context_identity_value(context, "run_id", "") or None,
            repo_id=context_identity_value(context, "repo_id", "") or None,
            timeout_seconds=context_lock_timeout_seconds(),
        )
    )


def release_context_locks(locks: list[RuntimeLock]) -> None:
    for runtime_lock in reversed(locks):
        runtime_lock.release()


def unique_append(values: list[str], additions: list[str]) -> list[str]:
    result = list(values)
    for item in additions:
        if item and item not in result:
            result.append(item)
    return result


def add_required_routes(required_route_sequence: list[str], additions: list[str]) -> list[str]:
    required = list(required_route_sequence)
    for route in additions:
        if not route:
            continue
        if route == "uigwe":
            required = [item for item in required if item != "uigwe"]
            if "seungjeongwon" in required:
                required.insert(required.index("seungjeongwon"), "uigwe")
            else:
                required.append("uigwe")
        elif route not in required:
            required.append(route)
    return required


def add_goal_bearing_execution_defaults(
    required_route_sequence: list[str],
    pending_gates: list[str],
    *,
    goal_bearing: bool,
) -> tuple[list[str], list[str]]:
    required = list(required_route_sequence)
    pending = list(pending_gates)
    if goal_bearing:
        required = unique_append(required, ["seungjeongwon"])
        pending = unique_append(pending, [SEUNGJEONGWON_RECEIPT_GATE])
    return required, pending


def synchronize_uigwe_promotion_gate(
    pending_gates: list[str],
    *,
    require_uigwe_now: bool,
    uigwe_entry_recorded: bool,
) -> list[str]:
    if uigwe_entry_recorded:
        return [gate for gate in pending_gates if gate != UIGWE_PROMOTION_GATE]
    if require_uigwe_now:
        pending = list(pending_gates)
        if UIGWE_PROMOTION_GATE not in pending:
            if SEUNGJEONGWON_RECEIPT_GATE in pending:
                pending.insert(pending.index(SEUNGJEONGWON_RECEIPT_GATE), UIGWE_PROMOTION_GATE)
            else:
                pending.append(UIGWE_PROMOTION_GATE)
        return pending
    return list(pending_gates)


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
    for field in REQUIRED_STRING_FIELDS:
        if field in context and (not isinstance(context[field], str) or not context[field]):
            failures.append(f"{field} must be a non-empty string")
    if context.get("format") != FORMAT:
        failures.append("unexpected format")
    current_surface = context.get("current_surface")
    if not isinstance(current_surface, str) or current_surface not in SURFACES:
        failures.append(f"invalid current_surface: {context.get('current_surface')}")
    context_status = context.get("context_status", "active")
    if not isinstance(context_status, str) or context_status not in {"active", "paused", "completed", "closed"}:
        failures.append(f"invalid context_status: {context.get('context_status')}")
    if "context_revision" in context and (
        not isinstance(context["context_revision"], int)
        or isinstance(context["context_revision"], bool)
        or context["context_revision"] < 1
    ):
        failures.append("context_revision must be a positive integer")
    if "objective_id" in context and (not isinstance(context["objective_id"], str) or not context["objective_id"]):
        failures.append("objective_id must be a non-empty string")
    if "task_class" in context and (not isinstance(context["task_class"], str) or not context["task_class"]):
        failures.append("task_class must be a non-empty string")
    if "projection_profile" in context and (
        not isinstance(context["projection_profile"], str)
        or context["projection_profile"] not in PROJECTION_PROFILES
    ):
        failures.append(f"invalid projection_profile: {context['projection_profile']}")
    for field in LIST_FIELDS:
        if field in context and not isinstance(context[field], list):
            failures.append(f"{field} must be a list")
        elif field in context:
            invalid_items = [item for item in context[field] if not isinstance(item, str) or not item]
            if invalid_items:
                failures.append(f"{field} must contain only non-empty strings")
    return failures


def context_run_path(context: dict[str, Any], *, sejong_home: Path | None = None) -> Path:
    run_id = context["run_id"]
    repo_id = context["repo_id"]
    return (sejong_home or sejong_root()) / "runs" / repo_id / run_id / "king-sejong-context.json"


@dataclass(frozen=True, slots=True)
class ContextRevisionConflict(Exception):
    expected: int
    actual: int

    def __str__(self) -> str:
        return f"context revision conflict: expected={self.expected}; actual={self.actual}"


@dataclass(frozen=True, slots=True)
class ContextIdentityConflict(Exception):
    field: str
    expected: Any
    actual: Any

    def __str__(self) -> str:
        return (
            "context identity conflict: "
            f"field={self.field}; expected={self.expected!r}; actual={self.actual!r}"
        )


def save_context(
    context: dict[str, Any],
    *,
    expected_context_revision: int | None = None,
    operation: str = "save context",
    sejong_home: Path | None = None,
    update_repo_index_after_commit: bool = True,
) -> Path:
    if expected_context_revision is None:
        raise ValueError("expected_context_revision is required")
    if (
        isinstance(expected_context_revision, bool)
        or not isinstance(expected_context_revision, int)
        or expected_context_revision < 0
    ):
        raise ValueError("expected_context_revision must be a non-negative integer")
    runtime_root = sejong_home or sejong_root()
    locks: list[RuntimeLock] = []
    try:
        locks.append(acquire_run_context_lock(context, operation, sejong_home=runtime_root))
        run_path = context_run_path(context, sejong_home=runtime_root)
        actual_revision = 0
        if run_path.exists():
            existing = load_json(run_path)
            for field in ("active_context_id", "repo_id", "run_id"):
                if existing.get(field) != context.get(field):
                    raise ContextIdentityConflict(field, existing.get(field), context.get(field))
            actual_revision = int(existing.get("context_revision", 0))
        if actual_revision != expected_context_revision:
            raise ContextRevisionConflict(expected_context_revision, actual_revision)
        updated = dict(context)
        updated["context_revision"] = actual_revision + 1
        updated["last_updated_at"] = now_utc()
        write_json(run_path, updated)
        context.clear()
        context.update(updated)
        if update_repo_index_after_commit:
            try:
                update_repo_index(runtime_root, context, run_path)
            except (
                InvalidBinding,
                RuntimeLockReleaseError,
                RuntimeLockTimeout,
                KeyError,
                OSError,
                TypeError,
                UnicodeError,
                ValueError,
            ) as error:
                print(
                    f"warning: repo index update failed after the Context commit: {type(error).__name__}: {error}",
                    file=sys.stderr,
                )
        return run_path
    finally:
        release_context_locks(locks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage durable King Sejong Contexts and Codex session bindings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a durable Context and a new exact session binding.")
    start.add_argument("--repo-root", default=".")
    start.add_argument("--additional-repo-root", action="append", dest="additional_repo_roots")
    start.add_argument("--repo-id")
    start.add_argument("--run-id")
    start.add_argument("--session-id")
    start.add_argument("--route-id")
    start.add_argument("--objective-id")
    start.add_argument("--objective-ref", action="append", dest="objective_refs")
    start.add_argument("--task-class")
    start.add_argument("--projection-profile", choices=sorted(PROJECTION_PROFILES))
    start.add_argument("--current-surface", default="sejong", choices=sorted(SURFACES))
    start.add_argument("--route", action="append", dest="route_sequence")
    start.add_argument(
        "--required-route",
        action="append",
        dest="required_route_sequence",
        help="Require a route. Requiring Uigwe adds its promotion gate until route entry.",
    )
    start.add_argument("--pending-gate", action="append", dest="pending_gates")
    start.add_argument(
        "--goal-bearing",
        action="store_true",
        help="Mark an outcome-completion workflow; adds Seungjeongwon and the receipt gate.",
    )
    start.add_argument("--protected-path", action="append", dest="protected_paths")
    start.add_argument("--allowed-direct-change-type", action="append", dest="allowed_direct_change_types")
    start.add_argument("--last-user-intent", default="King Sejong workflow started.")
    start.set_defaults(func=start_context)

    update = subparsers.add_parser("update", help="Update a durable King Sejong Context.")
    update.add_argument("--context")
    update.add_argument("--session-id")
    update.add_argument("--expect-context-revision", type=int)
    update.add_argument("--current-surface", choices=sorted(SURFACES))
    update.add_argument("--append-route", action="append", dest="append_routes")
    update.add_argument("--set-route-sequence", action="append", dest="set_route_sequence")
    update.add_argument(
        "--add-required-route",
        action="append",
        dest="add_required_routes",
        help="Add a required route. Adding Uigwe adds its promotion gate until route entry.",
    )
    update.add_argument("--add-pending-gate", action="append", dest="add_pending_gates")
    update.add_argument(
        "--require-seungjeongwon-receipt",
        action="store_true",
        help="Require a Seungjeongwon execution receipt before write-like execution.",
    )
    update.add_argument(
        "--clear-pending-gate",
        action="append",
        dest="clear_pending_gates",
        help=(
            "Clear a pending gate. Clearing uigwe_promotion_required before Uigwe entry also removes "
            "the unsatisfied Uigwe required route."
        ),
    )
    update.add_argument("--add-protected-path", action="append", dest="add_protected_paths")
    update.add_argument("--objective-id")
    update.add_argument("--add-objective-ref", action="append", dest="add_objective_refs")
    update.add_argument("--task-class")
    update.add_argument("--projection-profile", choices=sorted(PROJECTION_PROFILES))
    update.add_argument("--add-evidence-ref", action="append", dest="add_evidence_refs")
    update.add_argument("--add-artifact-ref", action="append", dest="add_artifact_refs")
    update.add_argument("--add-team-run-ref", action="append", dest="add_team_run_refs")
    update.add_argument("--add-subagent-ref", action="append", dest="add_subagent_refs")
    update.add_argument("--last-user-intent")
    update.set_defaults(func=update_context)

    doctor = subparsers.add_parser("doctor", help="Validate a durable King Sejong Context.")
    doctor.add_argument("--context")
    doctor.add_argument("--session-id")
    doctor.add_argument("--repo-root")
    doctor.set_defaults(func=doctor_context)

    repair = subparsers.add_parser("repair", help="Repair simple durable Context shape drift.")
    repair.add_argument("--context")
    repair.add_argument("--session-id")
    repair.add_argument("--expect-context-revision", type=int)
    repair.set_defaults(func=repair_context)

    close = subparsers.add_parser("close", help="Unbind the exact session and mark its Context closed.")
    close.add_argument("--context")
    close.add_argument("--session-id", required=True)
    close.add_argument("--turn-id")
    close.add_argument("--expect-revision", required=True, type=int)

    resume = subparsers.add_parser("resume", help="Explicitly bind a session to a durable context.")
    resume.add_argument("--context", required=True)
    resume.add_argument("--session-id", required=True)
    resume.add_argument("--turn-id")
    resume.add_argument("--host-namespace", default="codex")
    resume.add_argument("--expect-revision", required=True, type=int)
    resume.set_defaults(func=resume_context)

    unbind = subparsers.add_parser("unbind", help="Replace a session binding with an unbound tombstone.")
    unbind.add_argument("--session-id", required=True)
    unbind.add_argument("--turn-id")
    unbind.add_argument("--host-namespace", default="codex")
    unbind.add_argument("--expect-revision", required=True, type=int)
    unbind.set_defaults(func=unbind_context)

    observe = subparsers.add_parser("observe", help=argparse.SUPPRESS)
    observe.add_argument("--session-id", required=True)
    observe.add_argument("--turn-id", required=True)
    observe.add_argument("--host-namespace", default="codex")
    observe.add_argument("--expect-context-id", required=True)
    observe.add_argument("--expect-binding-epoch", required=True, type=int)
    observe.set_defaults(func=observe_context_binding)

    migrate = subparsers.add_parser(
        "migrate-legacy",
        help="Preserve the legacy active pointer as non-authoritative migration history.",
    )
    migrate.set_defaults(func=migrate_legacy_context)
    close.set_defaults(func=close_context)

    return parser


def emit_binding_warnings(binding: dict[str, Any]) -> None:
    warnings = binding.get(DERIVED_STATE_WARNINGS_FIELD)
    if not isinstance(warnings, list):
        return
    for warning in warnings:
        if isinstance(warning, str) and warning:
            print(f"warning: {warning}", file=sys.stderr)


def start_context(args: argparse.Namespace) -> int:
    repo_root = resolve_path(args.repo_root)
    run_id = args.run_id or default_run_id()
    repo_id = args.repo_id or repo_slug(repo_root)
    route_sequence = args.route_sequence or [args.current_surface]
    required_route_sequence, pending_gates = add_goal_bearing_execution_defaults(
        add_required_routes([], args.required_route_sequence or []),
        args.pending_gates or [],
        goal_bearing=args.goal_bearing,
    )
    pending_gates = synchronize_uigwe_promotion_gate(
        pending_gates,
        require_uigwe_now="uigwe" in required_route_sequence,
        uigwe_entry_recorded="uigwe" in route_sequence,
    )
    session_id = args.session_id or f"session-{run_id}"
    repo_roots = [repo_root, *(resolve_path(path) for path in (args.additional_repo_roots or []))]
    repo_identities = list(dict.fromkeys(repo_identity(path) for path in repo_roots))
    context = {
        "format": FORMAT,
        "active_context_id": f"ctx-{run_id}",
        "repo_id": repo_id,
        "repo_root": str(repo_root),
        "run_id": run_id,
        "session_id": session_id,
        "repo_identities": repo_identities,
        "context_status": "active",
        "route_id": args.route_id or f"route-{run_id}",
        **({"objective_id": args.objective_id} if args.objective_id else {}),
        **({"objective_refs": args.objective_refs} if args.objective_refs else {}),
        **({"task_class": args.task_class} if args.task_class else {}),
        **({"projection_profile": args.projection_profile} if args.projection_profile else {}),
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
    run_path = save_context(context, expected_context_revision=0, operation="start context")
    binding = bind_context(sejong_root(), session_id, run_path, expected_revision=0)
    emit_binding_warnings(binding)
    print(f"run_context={run_path}")
    print(f"session_binding={binding['binding_id']}")
    return 0


def load_context_argument(path: str | None, session_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    if path:
        context_path = Path(path).expanduser()
    elif session_id:
        context = resolve_bound_context(sejong_root(), session_id, observe=False)
        if not context:
            raise SystemExit(f"session has no active context binding: {session_id}")
        context_path = context_run_path(context)
        context.pop("_king_sejong_binding_epoch", None)
        context.pop("_king_sejong_binding_revision", None)
        return context_path, context
    else:
        raise SystemExit("explicit --context or --session-id is required; legacy active pointer is non-authoritative")
    if not context_path.exists():
        raise SystemExit(f"active context does not exist: {context_path}")
    return context_path, load_json(context_path)


def update_context(args: argparse.Namespace) -> int:
    _, context = load_context_argument(args.context, args.session_id)
    loaded_revision = int(context.get("context_revision", 0))
    uigwe_entry_recorded = (
        args.current_surface == "uigwe"
        or "uigwe" in (args.append_routes or [])
        or bool(args.set_route_sequence and args.set_route_sequence[-1] == "uigwe")
    )
    if args.current_surface:
        context["current_surface"] = args.current_surface
    if args.set_route_sequence:
        context["route_sequence"] = args.set_route_sequence
    if args.append_routes:
        context["route_sequence"] = unique_append(context.get("route_sequence", []), args.append_routes)
    if args.add_required_routes:
        context["required_route_sequence"] = add_required_routes(
            context.get("required_route_sequence", []),
            args.add_required_routes,
        )
    if "uigwe" in (args.add_required_routes or []) or uigwe_entry_recorded:
        context["pending_gates"] = synchronize_uigwe_promotion_gate(
            context.get("pending_gates", []),
            require_uigwe_now="uigwe" in (args.add_required_routes or []),
            uigwe_entry_recorded=uigwe_entry_recorded,
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
        uigwe_gate_was_pending = UIGWE_PROMOTION_GATE in context.get("pending_gates", [])
        context["pending_gates"] = [gate for gate in context.get("pending_gates", []) if gate not in clear]
        if UIGWE_PROMOTION_GATE in clear and uigwe_gate_was_pending and not uigwe_entry_recorded:
            context["required_route_sequence"] = [
                route for route in context.get("required_route_sequence", []) if route != "uigwe"
            ]
    if args.add_protected_paths:
        context["protected_paths"] = unique_append(context.get("protected_paths", []), args.add_protected_paths)
    if args.objective_id:
        context["objective_id"] = args.objective_id
    if args.add_objective_refs:
        context["objective_refs"] = unique_append(context.get("objective_refs", []), args.add_objective_refs)
    if args.task_class:
        context["task_class"] = args.task_class
    if args.projection_profile:
        context["projection_profile"] = args.projection_profile
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
    expected_revision = args.expect_context_revision if args.expect_context_revision is not None else loaded_revision
    run_path = save_context(context, expected_context_revision=expected_revision, operation="update context")
    print(f"context updated: {run_path}")
    return 0


def doctor_context(args: argparse.Namespace) -> int:
    context_path, context = load_context_argument(args.context, args.session_id)
    failures = validate_context(context)
    if args.repo_root:
        repo_root = resolve_path(args.repo_root)
        identities = context.get("repo_identities") or [declared_repo_identity(context.get("repo_root", ""))]
        if repo_identity(repo_root) not in identities:
            failures.append(
                "context repo identity does not match requested repo: "
                f"{repo_root}; context_repo_identities={','.join(identities)}"
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
    _, context = load_context_argument(args.context, args.session_id)
    loaded_revision = int(context.get("context_revision", 0))
    repaired = normalize_context_string_lists(context)
    failures = validate_context(repaired)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    run_path_exists = context_run_path(repaired).exists()
    expected_revision = (
        args.expect_context_revision
        if args.expect_context_revision is not None
        else loaded_revision if run_path_exists else 0
    )
    run_path = save_context(repaired, expected_context_revision=expected_revision, operation="repair context")
    print(f"context repaired: {run_path}")
    return 0


def close_context(args: argparse.Namespace) -> int:
    context_path, context = load_context_argument(args.context, args.session_id)
    failures = validate_context(context)
    if failures:
        raise InvalidBinding(f"invalid durable context: {context_path}: {', '.join(failures)}")
    binding = load_binding(sejong_root(), args.session_id)
    if (
        not binding
        or binding.get("state") != "bound"
        or binding.get("active_context_id") != context.get("active_context_id")
        or Path(str(binding.get("context_ref"))).expanduser().resolve() != context_path.expanduser().resolve()
    ):
        raise InvalidBinding(
            f"session binding does not reference requested Context: session_id={args.session_id}; "
            f"context={context_path}"
        )
    loaded_revision = int(context.get("context_revision", 0))
    binding = unbind_session(
        sejong_root(),
        args.session_id,
        turn_id=args.turn_id,
        expected_revision=args.expect_revision,
    )
    emit_binding_warnings(binding)
    context["context_status"] = "closed"
    save_context(context, expected_context_revision=loaded_revision, operation="close context")
    print(f"context closed: {context['active_context_id']}")
    return 0


def resume_context(args: argparse.Namespace) -> int:
    binding = bind_context(
        sejong_root(),
        args.session_id,
        Path(args.context),
        turn_id=args.turn_id,
        namespace=args.host_namespace,
        expected_revision=args.expect_revision,
    )
    emit_binding_warnings(binding)
    print(f"context resumed: {binding['active_context_id']}")
    print(f"binding_epoch={binding['binding_epoch']}")
    print(f"binding_revision={binding['revision']}")
    return 0


def unbind_context(args: argparse.Namespace) -> int:
    binding = unbind_session(
        sejong_root(),
        args.session_id,
        turn_id=args.turn_id,
        namespace=args.host_namespace,
        expected_revision=args.expect_revision,
    )
    emit_binding_warnings(binding)
    print(f"session unbound: {args.session_id}")
    print(f"binding_epoch={binding['binding_epoch']}")
    print(f"binding_revision={binding['revision']}")
    return 0


def observe_context_binding(args: argparse.Namespace) -> int:
    binding = observe_binding(
        sejong_root(),
        args.session_id,
        args.turn_id,
        args.expect_context_id,
        args.expect_binding_epoch,
        namespace=args.host_namespace,
    )
    print(f"binding observed: {binding['active_context_id']}")
    print(f"binding_revision={binding['revision']}")
    return 0


def migrate_legacy_context(args: argparse.Namespace) -> int:
    path = migrate_legacy_pointer(sejong_root())
    print(f"legacy migration recorded: {path}")
    print("automatic_injection_authority=false")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (
        BindingRevisionConflict,
        ContextIdentityConflict,
        ContextRevisionConflict,
        InvalidBinding,
        InvalidContextLockTimeout,
        RuntimeLockReleaseError,
        RuntimeLockTimeout,
        StaleBindingObservation,
    ) as error:
        print(f"failure: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
