#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEAM_FORMAT = "sejong.team/v0.1-draft"
ROUNDS_FORMAT = "sejong.team-rounds/v0.1-draft"
LEASES_FORMAT = "sejong.team-leases/v0.1-draft"
WORKER_FORMAT = "sejong.team-worker/v0.1-draft"
MAILBOX_MESSAGE_FORMAT = "sejong.team-mailbox-message/v0.1-draft"
MAILBOX_RECEIVE_FORMAT = "sejong.team-mailbox-receive/v0.1-draft"

MESSAGE_KINDS = {
    "claim",
    "objection",
    "question",
    "response",
    "evidence_ref",
    "risk",
    "status",
    "blocker",
    "verification",
}

MESSAGE_DIRECTIONS = {
    "lead_to_worker",
    "worker_to_lead",
    "worker_to_worker",
    "system",
}

ENDPOINT_TYPES = {
    "lead",
    "worker",
    "system",
}

REQUIRED_MAILBOX_FIELDS = (
    "format",
    "message_id",
    "run_id",
    "round_id",
    "thread_id",
    "target_message_id",
    "direction",
    "sender",
    "recipients",
    "kind",
    "summary",
    "body",
    "evidence_refs",
    "requires_response",
    "created_at",
)

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

DEFAULT_PHASE_LABELS = {
    "sejong": "King Sejong workflow",
    "jangyeongsil": "research",
    "jiphyeonjeon": "decision",
    "uigwe": "planning",
    "seungjeongwon": "execution",
    "sillok": "recording",
    "danjong": "retired option",
    "sejong-direct": "direct handling",
}

FORBIDDEN_WORKER_AUTHORITY_TERMS = (
    "approve the uigwe gate",
    "approved the uigwe gate",
    "uigwe gate approved",
    "gate approved",
    "final decision",
    "final synthesis",
    "majority vote",
    "by majority",
    "consensus approves",
)

GLOB_CHARS = "*?["


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sejong_root() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def state_root() -> Path:
    return sejong_root() / "state" / "team"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, sort_keys=True) + "\n")


def require_run_dir(run_dir: Path) -> Path:
    resolved = run_dir.expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"team run directory does not exist: {resolved}")
    return resolved


def parse_worker(value: str) -> dict[str, str]:
    parts = value.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError("worker must be worker_id:role:scope")
    return {"worker_id": parts[0], "role": parts[1], "scope": parts[2]}


def parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("assignment must be worker_id=value")
    key, assigned = value.split("=", 1)
    if not key or not assigned:
        raise argparse.ArgumentTypeError("assignment must be worker_id=value")
    return key, assigned


def parse_endpoint(value: str) -> dict[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError("endpoint must be type:id")
    endpoint_type, endpoint_id = parts
    if endpoint_type not in ENDPOINT_TYPES:
        raise argparse.ArgumentTypeError(f"endpoint type must be one of: {', '.join(sorted(ENDPOINT_TYPES))}")
    return {"type": endpoint_type, "id": endpoint_id}


def grouped_assignments(assignments: list[tuple[str, str]] | None) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key, value in assignments or []:
        grouped.setdefault(key, []).append(value)
    return grouped


def single_assignments(assignments: list[tuple[str, str]] | None) -> dict[str, str]:
    singles: dict[str, str] = {}
    for key, value in assignments or []:
        singles[key] = value
    return singles


def normalize_scope(scope: str) -> str:
    normalized = scope.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    return normalized or "."


def is_glob_scope(scope: str) -> bool:
    return any(char in scope for char in GLOB_CHARS)


def literal_scope_prefix(scope: str) -> str:
    normalized = normalize_scope(scope)
    first_glob = min((normalized.find(char) for char in GLOB_CHARS if char in normalized), default=-1)
    if first_glob == -1:
        return normalized
    prefix = normalized[:first_glob]
    if "/" in prefix:
        prefix = prefix.rsplit("/", 1)[0]
    return prefix.rstrip("/") or "."


def path_prefixes_overlap(left: str, right: str) -> bool:
    left = normalize_scope(left)
    right = normalize_scope(right)
    if left == "." or right == ".":
        return True
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def scope_matches(pattern: str, target: str) -> bool:
    pattern = normalize_scope(pattern)
    target = normalize_scope(target)
    return fnmatch.fnmatchcase(target, pattern) or path_prefixes_overlap(literal_scope_prefix(pattern), target)


def scopes_overlap(left: str, right: str) -> bool:
    left = normalize_scope(left)
    right = normalize_scope(right)
    left_is_glob = is_glob_scope(left)
    right_is_glob = is_glob_scope(right)
    if not left_is_glob and not right_is_glob:
        return path_prefixes_overlap(left, right)
    if left_is_glob and not right_is_glob:
        return scope_matches(left, right)
    if right_is_glob and not left_is_glob:
        return scope_matches(right, left)
    return path_prefixes_overlap(literal_scope_prefix(left), literal_scope_prefix(right))


def team_path(run_dir: Path) -> Path:
    return run_dir / "team.json"


def rounds_path(run_dir: Path) -> Path:
    return run_dir / "rounds.json"


def leases_path(run_dir: Path) -> Path:
    return run_dir / "leases.json"


def worker_state_path(run_dir: Path, worker_id: str) -> Path:
    return run_dir / "workers" / worker_id / "state.json"


def mailbox_path(run_dir: Path) -> Path:
    return run_dir / "mailbox.jsonl"


def load_team(run_dir: Path) -> dict[str, Any]:
    return load_json(team_path(run_dir))


def save_team(run_dir: Path, team: dict[str, Any]) -> None:
    write_json(team_path(run_dir), team)


def worker_ids(team: dict[str, Any]) -> set[str]:
    return {worker["worker_id"] for worker in team.get("workers", [])}


def worker_by_id(team: dict[str, Any], worker_id: str) -> dict[str, Any] | None:
    for worker in team.get("workers", []):
        if worker.get("worker_id") == worker_id:
            return worker
    return None


def default_allowed_outputs(worker: dict[str, str]) -> list[str]:
    return [f"bounded {worker['role']} output for {worker['scope']}"]


def default_verification_expectation(worker: dict[str, str]) -> str:
    return f"Return evidence or a blocker for {worker['scope']}."


def default_stop_condition(worker: dict[str, str]) -> str:
    return "Stop after returning the assigned output to the Sejong lead."


def add_worker_record(
    run_dir: Path,
    worker: dict[str, str],
    command: str | None = None,
    *,
    allowed_outputs: list[str] | None = None,
    verification_expectation: str | None = None,
    stop_condition: str | None = None,
) -> None:
    team = load_team(run_dir)
    for required_field in ("current_surface", "phase_label"):
        if not team.get(required_field):
            raise SystemExit(f"team run missing {required_field}; initialize a court-mode-aware run first")
    if worker["worker_id"] in worker_ids(team):
        raise SystemExit(f"worker already exists: {worker['worker_id']}")

    record: dict[str, Any] = {
        "worker_id": worker["worker_id"],
        "role": worker["role"],
        "scope": worker["scope"],
        "allowed_message_kinds": sorted(MESSAGE_KINDS),
        "allowed_outputs": allowed_outputs or default_allowed_outputs(worker),
        "verification_expectation": verification_expectation or default_verification_expectation(worker),
        "stop_condition": stop_condition or default_stop_condition(worker),
        "status": "registered",
    }
    if command:
        record["command"] = command

    team.setdefault("workers", []).append(record)
    save_team(run_dir, team)

    worker_dir = run_dir / "workers" / worker["worker_id"]
    worker_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        worker_dir / "state.json",
        {
            "format": WORKER_FORMAT,
            "run_id": team["run_id"],
            "current_surface": team["current_surface"],
            "phase_label": team["phase_label"],
            "worker_id": worker["worker_id"],
            "role": worker["role"],
            "scope": worker["scope"],
            "allowed_outputs": record["allowed_outputs"],
            "verification_expectation": record["verification_expectation"],
            "stop_condition": record["stop_condition"],
            "status": "registered",
            "updated_at": now_utc(),
        },
    )
    notes_path = worker_dir / "notes.md"
    if not notes_path.exists():
        notes_path.write_text(f"# {worker['worker_id']} Notes\n", encoding="utf-8")
    (run_dir / "artifacts" / worker["worker_id"]).mkdir(parents=True, exist_ok=True)


def init_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or default_run_id()
    run_dir = (state_root() / run_id).expanduser()
    if run_dir.exists() and not args.force:
        raise SystemExit(f"team run already exists: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "workers").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)

    if args.brief_file:
        brief = Path(args.brief_file).read_text(encoding="utf-8")
    elif args.brief:
        brief = args.brief
    else:
        brief = "# Team Brief\n\n- Source of truth:\n- Decision question:\n- Fixed options:\n- Stop condition:\n"
    (run_dir / "brief.md").write_text(brief.rstrip() + "\n", encoding="utf-8")

    repo_root = Path(args.repo_root).expanduser().resolve()
    source_of_truth_refs = args.source_of_truth_ref or ["brief.md"]
    current_surface = args.current_surface
    phase_label = args.phase_label or DEFAULT_PHASE_LABELS[current_surface]
    route_sequence = args.route_sequence or [current_surface]
    write_json(
        team_path(run_dir),
        {
            "format": TEAM_FORMAT,
            "run_id": run_id,
            "created_at": now_utc(),
            "repo_root": str(repo_root),
            "brief_path": "brief.md",
            "active_context_id": args.active_context_id or f"ctx-{run_id}",
            "route_id": args.route_id or f"route-{run_id}",
            "current_surface": current_surface,
            "phase_label": phase_label,
            "route_sequence": route_sequence,
            "pending_gates": args.pending_gate or [],
            "source_of_truth_refs": source_of_truth_refs,
            "lead_authority": {
                "gate_owner": "sejong",
                "synthesis_owner": "sejong",
                "final_verification_owner": "seungjeongwon",
            },
            "forbidden_worker_claims": [
                "gate approval",
                "final decision by majority",
            ],
            "workers": [],
        },
    )
    write_json(rounds_path(run_dir), {"format": ROUNDS_FORMAT, "run_id": run_id, "rounds": []})
    write_json(leases_path(run_dir), {"format": LEASES_FORMAT, "run_id": run_id, "leases": []})
    mailbox_path(run_dir).write_text("", encoding="utf-8")

    commands = dict(args.command or [])
    allowed_outputs = grouped_assignments(args.worker_allowed_output)
    verification_expectations = single_assignments(args.worker_verification)
    stop_conditions = single_assignments(args.worker_stop)
    declared_worker_ids = {worker["worker_id"] for worker in args.worker or []}
    assigned_worker_ids = set(commands) | set(allowed_outputs) | set(verification_expectations) | set(stop_conditions)
    unknown_worker_ids = sorted(assigned_worker_ids - declared_worker_ids)
    if unknown_worker_ids:
        raise SystemExit(f"worker assignments reference unknown workers: {unknown_worker_ids}")
    for worker in args.worker or []:
        worker_id = worker["worker_id"]
        add_worker_record(
            run_dir,
            worker,
            commands.get(worker_id),
            allowed_outputs=allowed_outputs.get(worker_id),
            verification_expectation=verification_expectations.get(worker_id),
            stop_condition=stop_conditions.get(worker_id),
        )

    print(str(run_dir))
    return 0


def add_worker(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    add_worker_record(
        run_dir,
        args.worker,
        args.command,
        allowed_outputs=args.allowed_output,
        verification_expectation=args.verification,
        stop_condition=args.stop,
    )
    print(f"worker added: {args.worker['worker_id']}")
    return 0


def open_round(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    rounds = load_json(rounds_path(run_dir))
    round_id = args.round_id or f"round-{len(rounds.get('rounds', [])) + 1}"
    if any(item["round_id"] == round_id for item in rounds.get("rounds", [])):
        raise SystemExit(f"round already exists: {round_id}")
    rounds.setdefault("rounds", []).append(
        {
            "round_id": round_id,
            "status": "open",
            "purpose": args.purpose,
            "opened_at": now_utc(),
            "closed_at": None,
        }
    )
    write_json(rounds_path(run_dir), rounds)
    print(f"round opened: {round_id}")
    return 0


def close_round(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    rounds = load_json(rounds_path(run_dir))
    for item in rounds.get("rounds", []):
        if item["round_id"] == args.round_id:
            if item["status"] == "closed":
                raise SystemExit(f"round already closed: {args.round_id}")
            item["status"] = "closed"
            item["closed_at"] = now_utc()
            write_json(rounds_path(run_dir), rounds)
            print(f"round closed: {args.round_id}")
            return 0
    raise SystemExit(f"unknown round: {args.round_id}")


def current_open_round(run_dir: Path) -> str:
    rounds = load_json(rounds_path(run_dir)).get("rounds", [])
    for item in reversed(rounds):
        if item.get("status") == "open":
            return item["round_id"]
    raise SystemExit("no open round; run open-round first or pass --round-id")


def require_open_round(run_dir: Path, round_id: str) -> None:
    rounds = load_json(rounds_path(run_dir)).get("rounds", [])
    for item in rounds:
        if item.get("round_id") == round_id:
            if item.get("status") != "open":
                raise SystemExit(f"round is not open: {round_id}")
            return
    raise SystemExit(f"unknown round: {round_id}")


def worker_endpoint(worker_id: str, worker: dict[str, Any]) -> dict[str, str]:
    return {
        "type": "worker",
        "id": worker_id,
        "role": str(worker.get("role") or ""),
        "scope": str(worker.get("scope") or ""),
    }


def normalize_endpoint(team: dict[str, Any], endpoint: dict[str, str]) -> dict[str, str]:
    normalized = dict(endpoint)
    endpoint_type = normalized.get("type")
    endpoint_id = normalized.get("id")
    if endpoint_type not in ENDPOINT_TYPES:
        raise SystemExit(f"unsupported endpoint type: {endpoint_type}")
    if not endpoint_id:
        raise SystemExit("endpoint id is required")
    if endpoint_type == "worker":
        worker = worker_by_id(team, endpoint_id)
        if worker is None:
            raise SystemExit(f"recipient references unknown worker: {endpoint_id}")
        normalized.setdefault("role", str(worker.get("role") or ""))
        normalized.setdefault("scope", str(worker.get("scope") or ""))
    return normalized


def endpoint_key(endpoint: dict[str, Any]) -> tuple[str, str]:
    return str(endpoint.get("type") or ""), str(endpoint.get("id") or "")


def endpoint_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return endpoint_key(left) == endpoint_key(right)


def infer_direction(sender: dict[str, Any], recipients: list[dict[str, Any]]) -> str:
    sender_type = sender.get("type")
    recipient_types = {recipient.get("type") for recipient in recipients}
    if sender_type == "worker" and recipient_types == {"lead"}:
        return "worker_to_lead"
    if sender_type == "worker" and recipient_types == {"worker"}:
        return "worker_to_worker"
    if sender_type == "lead" and recipient_types == {"worker"}:
        return "lead_to_worker"
    if sender_type == "system":
        return "system"
    raise SystemExit("cannot infer mailbox direction from sender and recipients")


def direction_is_consistent(direction: str, sender: dict[str, Any], recipients: list[dict[str, Any]]) -> bool:
    sender_type = sender.get("type")
    recipient_types = {recipient.get("type") for recipient in recipients}
    if direction == "worker_to_lead":
        return sender_type == "worker" and recipient_types == {"lead"}
    if direction == "worker_to_worker":
        return sender_type == "worker" and recipient_types == {"worker"}
    if direction == "lead_to_worker":
        return sender_type == "lead" and recipient_types == {"worker"}
    if direction == "system":
        return sender_type == "system"
    return False


def message_by_id(messages: list[dict[str, Any]], message_id: str | None) -> dict[str, Any] | None:
    if not message_id:
        return None
    for message in messages:
        if message.get("message_id") == message_id:
            return message
    return None


def send_message(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    worker = worker_by_id(team, args.worker_id)
    if worker is None:
        raise SystemExit(f"unknown worker: {args.worker_id}")
    if args.kind not in MESSAGE_KINDS:
        raise SystemExit(f"unsupported message kind: {args.kind}")
    if args.kind not in worker.get("allowed_message_kinds", []):
        raise SystemExit(f"message kind not allowed for worker {args.worker_id}: {args.kind}")

    role = args.role or worker["role"]
    scope = args.scope or worker["scope"]
    if role != worker["role"]:
        raise SystemExit(f"message role does not match registered worker role: {role} != {worker['role']}")
    if scope != worker["scope"]:
        raise SystemExit(f"message scope does not match registered worker scope: {scope} != {worker['scope']}")

    round_id = args.round_id or current_open_round(run_dir)
    require_open_round(run_dir, round_id)
    existing_messages = read_mailbox(run_dir)
    target = message_by_id(existing_messages, args.target_message_id)
    if args.target_message_id and target is None:
        raise SystemExit(f"target_message_id not found before send: {args.target_message_id}")

    message_id = args.message_id or f"{round_id}-{args.worker_id}-{len(existing_messages) + 1}"
    sender = worker_endpoint(args.worker_id, {"role": role, "scope": scope})
    recipients = [normalize_endpoint(team, recipient) for recipient in (args.recipient or [{"type": "lead", "id": "sejong"}])]
    direction = args.direction or infer_direction(sender, recipients)
    if direction not in MESSAGE_DIRECTIONS:
        raise SystemExit(f"unsupported message direction: {direction}")
    if not direction_is_consistent(direction, sender, recipients):
        raise SystemExit(f"message direction is inconsistent with sender and recipients: {direction}")
    thread_id = args.thread_id or (target.get("thread_id") if target else None) or message_id

    message = {
        "format": MAILBOX_MESSAGE_FORMAT,
        "message_id": message_id,
        "run_id": team["run_id"],
        "round_id": round_id,
        "thread_id": thread_id,
        "target_message_id": args.target_message_id,
        "direction": direction,
        "sender": sender,
        "recipients": recipients,
        "kind": args.kind,
        "summary": args.summary,
        "body": args.body,
        "evidence_refs": args.evidence_ref or [],
        "requires_response": args.requires_response,
        "created_at": now_utc(),
    }
    append_jsonl(mailbox_path(run_dir), message)
    print(f"message sent: {message_id}")
    return 0


def append_message(args: argparse.Namespace) -> int:
    return send_message(args)


def acquire_lease(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    if args.worker_id not in worker_ids(team):
        raise SystemExit(f"unknown worker: {args.worker_id}")
    leases = load_json(leases_path(run_dir))
    active = [lease for lease in leases.get("leases", []) if lease.get("status") == "active"]
    requested = [normalize_scope(scope) for scope in args.scope]
    for lease in active:
        if lease.get("worker_id") == args.worker_id:
            continue
        existing_scopes = [normalize_scope(scope) for scope in lease.get("scopes", [])]
        overlaps = sorted(
            {
                f"{requested_scope} overlaps {existing_scope}"
                for requested_scope in requested
                for existing_scope in existing_scopes
                if scopes_overlap(requested_scope, existing_scope)
            }
        )
        if overlaps:
            raise SystemExit(f"lease conflict with {lease.get('worker_id')}: {', '.join(overlaps)}")

    lease_id = args.lease_id or f"lease-{args.worker_id}-{len(leases.get('leases', [])) + 1}"
    leases.setdefault("leases", []).append(
        {
            "lease_id": lease_id,
            "worker_id": args.worker_id,
            "scopes": args.scope,
            "status": "active",
            "acquired_at": now_utc(),
            "released_at": None,
        }
    )
    write_json(leases_path(run_dir), leases)
    print(f"lease acquired: {lease_id}")
    return 0


def release_lease(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    leases = load_json(leases_path(run_dir))
    for lease in leases.get("leases", []):
        if lease["lease_id"] == args.lease_id:
            if lease["status"] == "released":
                raise SystemExit(f"lease already released: {args.lease_id}")
            lease["status"] = "released"
            lease["released_at"] = now_utc()
            write_json(leases_path(run_dir), leases)
            print(f"lease released: {args.lease_id}")
            return 0
    raise SystemExit(f"unknown lease: {args.lease_id}")


def read_mailbox(run_dir: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for line_no, line in enumerate(mailbox_path(run_dir).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid mailbox JSON at line {line_no}: {exc}") from exc
    return messages


def worker_claims_forbidden_authority(message: dict[str, Any]) -> bool:
    message_text = " ".join(
        [
            str(message.get("summary") or ""),
            str(message.get("body") or ""),
        ]
    ).lower()
    return any(term in message_text for term in FORBIDDEN_WORKER_AUTHORITY_TERMS)


def mailbox_message_failures(
    team: dict[str, Any],
    message: dict[str, Any],
    *,
    seen_messages: set[str],
    round_ids: set[str],
) -> list[str]:
    failures: list[str] = []
    message_id = str(message.get("message_id") or "")
    if message.get("format") != MAILBOX_MESSAGE_FORMAT:
        failures.append(f"mailbox message has unexpected format: {message_id or '<missing>'}")
    for field in REQUIRED_MAILBOX_FIELDS:
        if field not in message:
            failures.append(f"mailbox message missing {field}: {message_id or '<missing>'}")

    sender = message.get("sender") or {}
    recipients = message.get("recipients") or []
    direction = str(message.get("direction") or "")
    kind = message.get("kind")

    if not isinstance(sender, dict):
        failures.append(f"mailbox sender must be an object: {message_id}")
        sender = {}
    if not isinstance(recipients, list) or not recipients:
        failures.append(f"mailbox recipients must be a non-empty list: {message_id}")
        recipients = []
    if direction not in MESSAGE_DIRECTIONS:
        failures.append(f"unsupported mailbox direction: {message_id}")
    elif recipients and not direction_is_consistent(direction, sender, recipients):
        failures.append(f"mailbox direction does not match sender and recipients: {message_id}")

    sender_type = sender.get("type")
    sender_id = str(sender.get("id") or "")
    if sender_type not in ENDPOINT_TYPES:
        failures.append(f"mailbox sender has unsupported endpoint type: {message_id}")
    if not sender_id:
        failures.append(f"mailbox sender missing id: {message_id}")
    worker = worker_by_id(team, sender_id) if sender_type == "worker" else None
    if sender_type == "worker":
        if worker is None:
            failures.append(f"mailbox message references unknown worker: {message_id}")
        else:
            if sender.get("role") != worker.get("role"):
                failures.append(f"mailbox role does not match worker: {message_id}")
            if sender.get("scope") != worker.get("scope"):
                failures.append(f"mailbox scope does not match worker: {message_id}")
            if kind not in worker.get("allowed_message_kinds", []):
                failures.append(f"mailbox kind not allowed for worker: {message_id}")

    for recipient in recipients:
        if not isinstance(recipient, dict):
            failures.append(f"mailbox recipient must be an object: {message_id}")
            continue
        if recipient.get("type") not in ENDPOINT_TYPES:
            failures.append(f"mailbox recipient has unsupported endpoint type: {message_id}")
        if not recipient.get("id"):
            failures.append(f"mailbox recipient missing id: {message_id}")
        if recipient.get("type") == "worker" and worker_by_id(team, str(recipient.get("id") or "")) is None:
            failures.append(f"mailbox recipient references unknown worker: {message_id}")

    if kind not in MESSAGE_KINDS:
        failures.append(f"unsupported mailbox kind: {kind}")
    if not message_id:
        failures.append("mailbox message missing message_id")
    elif message_id in seen_messages:
        failures.append(f"duplicate message_id: {message_id}")
    else:
        target = message.get("target_message_id")
        if target and target not in seen_messages:
            failures.append(f"target_message_id not found before reply: {target}")
        seen_messages.add(message_id)
    if not message.get("thread_id"):
        failures.append(f"mailbox message missing thread_id: {message_id}")
    if message.get("round_id") not in round_ids:
        failures.append(f"mailbox message references unknown round: {message_id}")
    if not isinstance(message.get("evidence_refs"), list):
        failures.append(f"mailbox evidence_refs must be a list: {message_id}")
    if not isinstance(message.get("requires_response"), bool):
        failures.append(f"mailbox requires_response must be boolean: {message_id}")
    if worker_claims_forbidden_authority(message):
        failures.append(f"worker message claims gate or final authority: {message_id}")
    return failures


def source_ref_exists(run_dir: Path, ref: str) -> bool:
    candidate = Path(ref)
    if candidate.is_absolute():
        return candidate.exists()
    return (run_dir / candidate).exists()


def check_run(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    required = ["brief.md", "team.json", "rounds.json", "mailbox.jsonl", "leases.json"]
    failures: list[str] = []
    for name in required:
        if not (run_dir / name).exists():
            failures.append(f"missing {name}")

    team = load_team(run_dir)
    if team.get("format") != TEAM_FORMAT:
        failures.append("team.json has unexpected format")
    for required_field in (
        "active_context_id",
        "route_id",
        "current_surface",
        "phase_label",
        "route_sequence",
        "source_of_truth_refs",
        "lead_authority",
    ):
        if not team.get(required_field):
            failures.append(f"team.json missing {required_field}")
    if team.get("current_surface") not in SURFACES:
        failures.append(f"team.json has invalid current_surface: {team.get('current_surface')}")

    lead_authority = team.get("lead_authority") or {}
    if lead_authority.get("gate_owner") != "sejong":
        failures.append("lead_authority.gate_owner must be sejong")
    if lead_authority.get("synthesis_owner") != "sejong":
        failures.append("lead_authority.synthesis_owner must be sejong")
    if lead_authority.get("final_verification_owner") != "seungjeongwon":
        failures.append("lead_authority.final_verification_owner must be seungjeongwon")

    for ref in team.get("source_of_truth_refs") or []:
        if not source_ref_exists(run_dir, ref):
            failures.append(f"source_of_truth_ref does not exist: {ref}")

    for worker in team.get("workers", []):
        for field in (
            "worker_id",
            "role",
            "scope",
            "allowed_message_kinds",
            "allowed_outputs",
            "verification_expectation",
            "stop_condition",
            "status",
        ):
            if not worker.get(field):
                failures.append(f"worker missing {field}: {worker.get('worker_id')}")
        invalid_kinds = sorted(set(worker.get("allowed_message_kinds") or []) - MESSAGE_KINDS)
        if invalid_kinds:
            failures.append(f"worker has unsupported allowed_message_kinds: {worker.get('worker_id')}: {invalid_kinds}")

    round_ids = {str(item.get("round_id") or "") for item in load_json(rounds_path(run_dir)).get("rounds", [])}
    seen_messages: set[str] = set()
    for message in read_mailbox(run_dir):
        failures.extend(mailbox_message_failures(team, message, seen_messages=seen_messages, round_ids=round_ids))

    leases = load_json(leases_path(run_dir))
    active: dict[str, str] = {}
    for lease in leases.get("leases", []):
        if lease.get("status") != "active":
            continue
        for scope in lease.get("scopes", []):
            normalized_scope = normalize_scope(scope)
            for active_scope, owner in active.items():
                if owner != lease.get("worker_id") and scopes_overlap(normalized_scope, active_scope):
                    failures.append(
                        f"active lease conflict on {normalized_scope} and {active_scope}: "
                        f"{owner} and {lease.get('worker_id')}"
                    )
            active[normalized_scope] = lease.get("worker_id", "")

    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    print(f"team run ok: {run_dir}")
    return 0


def receive_messages(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    if args.worker_id and args.recipient:
        raise SystemExit("pass either --worker-id or --recipient, not both")
    if args.recipient:
        recipient = args.recipient
    elif args.worker_id:
        recipient = {"type": "worker", "id": args.worker_id}
    else:
        recipient = {"type": "lead", "id": "sejong"}
    recipient = normalize_endpoint(team, recipient)

    messages = read_mailbox(run_dir)
    if args.after_message_id and message_by_id(messages, args.after_message_id) is None:
        raise SystemExit(f"after_message_id not found: {args.after_message_id}")

    include = args.after_message_id is None
    selected: list[dict[str, Any]] = []
    for message in messages:
        if not include:
            include = message.get("message_id") == args.after_message_id
            continue
        if args.round_id and message.get("round_id") != args.round_id:
            continue
        if args.thread_id and message.get("thread_id") != args.thread_id:
            continue
        if args.kind and message.get("kind") != args.kind:
            continue
        recipients = message.get("recipients") or []
        if not any(endpoint_matches(recipient, item) for item in recipients if isinstance(item, dict)):
            continue
        selected.append(message)

    payload = {
        "format": MAILBOX_RECEIVE_FORMAT,
        "run_id": team["run_id"],
        "recipient": recipient,
        "after_message_id": args.after_message_id,
        "count": len(selected),
        "messages": selected,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def launch(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    commands = {
        worker["worker_id"]: worker["command"]
        for worker in team.get("workers", [])
        if worker.get("command")
    }
    commands.update(dict(args.worker_command or []))
    unknown = set(commands) - worker_ids(team)
    if unknown:
        raise SystemExit(f"commands reference unknown workers: {sorted(unknown)}")
    if not commands:
        raise SystemExit("at least one --worker-command worker_id=command is required")

    session = args.session or f"sejong-{team['run_id']}"
    cwd = str(Path(args.cwd or team["repo_root"]).expanduser().resolve())
    tmux_commands: list[list[str]] = []
    for index, (worker_id, command) in enumerate(commands.items()):
        worker = worker_by_id(team, worker_id) or {}
        env_values = {
            "SEJONG_TEAM_RUN": str(run_dir),
            "SEJONG_TEAM_WORKER": worker_id,
            "SEJONG_CURRENT_SURFACE": str(team.get("current_surface") or ""),
            "SEJONG_PHASE_LABEL": str(team.get("phase_label") or ""),
            "SEJONG_ROUTE_SEQUENCE": json.dumps(team.get("route_sequence") or []),
            "SEJONG_SOURCE_OF_TRUTH_REFS": json.dumps(team.get("source_of_truth_refs") or []),
            "SEJONG_PENDING_GATES": json.dumps(team.get("pending_gates") or []),
            "SEJONG_WORKER_ROLE": str(worker.get("role") or ""),
            "SEJONG_WORKER_SCOPE": str(worker.get("scope") or ""),
            "SEJONG_WORKER_ALLOWED_OUTPUTS": json.dumps(worker.get("allowed_outputs") or []),
            "SEJONG_WORKER_STOP_CONDITION": str(worker.get("stop_condition") or ""),
        }
        worker_env = " ".join(f"{key}={shlex.quote(value)}" for key, value in env_values.items())
        shell_command = f"{worker_env} {command}"
        if index == 0:
            tmux_commands.append(["tmux", "new-session", "-d", "-s", session, "-c", cwd, shell_command])
        else:
            tmux_commands.append(["tmux", "split-window", "-t", session, "-c", cwd, shell_command])
    tmux_commands.append(["tmux", "select-layout", "-t", session, "tiled"])

    if args.dry_run:
        for command in tmux_commands:
            print(" ".join(command))
        return 0

    for command in tmux_commands:
        subprocess.run(command, check=True)
    print(f"tmux session launched: {session}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Sejong TeamExecutor state and tmux worker launch metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a TeamExecutor run directory")
    init.add_argument("--run-id")
    init.add_argument("--repo-root", default=".")
    init.add_argument("--brief")
    init.add_argument("--brief-file")
    init.add_argument("--active-context-id")
    init.add_argument("--route-id")
    init.add_argument("--current-surface", required=True, choices=sorted(SURFACES))
    init.add_argument("--phase-label")
    init.add_argument("--route-sequence", action="append")
    init.add_argument("--pending-gate", action="append")
    init.add_argument("--source-of-truth-ref", action="append")
    init.add_argument("--worker", action="append", type=parse_worker)
    init.add_argument("--command", action="append", type=parse_assignment)
    init.add_argument("--worker-allowed-output", action="append", type=parse_assignment)
    init.add_argument("--worker-verification", action="append", type=parse_assignment)
    init.add_argument("--worker-stop", action="append", type=parse_assignment)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=init_run)

    worker = subparsers.add_parser("add-worker", help="Register a worker in an existing run")
    worker.add_argument("run_dir")
    worker.add_argument("worker", type=parse_worker)
    worker.add_argument("--command")
    worker.add_argument("--allowed-output", action="append")
    worker.add_argument("--verification")
    worker.add_argument("--stop")
    worker.set_defaults(func=add_worker)

    open_cmd = subparsers.add_parser("open-round", help="Open a mailbox challenge round")
    open_cmd.add_argument("run_dir")
    open_cmd.add_argument("--round-id")
    open_cmd.add_argument("--purpose", required=True)
    open_cmd.set_defaults(func=open_round)

    close_cmd = subparsers.add_parser("close-round", help="Close a mailbox challenge round")
    close_cmd.add_argument("run_dir")
    close_cmd.add_argument("round_id")
    close_cmd.set_defaults(func=close_round)

    send = subparsers.add_parser("send-message", help="Send one versioned mailbox message")
    send.add_argument("run_dir")
    send.add_argument("--message-id")
    send.add_argument("--round-id")
    send.add_argument("--thread-id")
    send.add_argument("--worker-id", required=True)
    send.add_argument("--role")
    send.add_argument("--scope")
    send.add_argument("--kind", required=True, choices=sorted(MESSAGE_KINDS))
    send.add_argument("--target-message-id")
    send.add_argument("--recipient", action="append", type=parse_endpoint)
    send.add_argument("--direction", choices=sorted(MESSAGE_DIRECTIONS))
    send.add_argument("--summary", required=True)
    send.add_argument("--body")
    send.add_argument("--evidence-ref", action="append")
    send.add_argument("--requires-response", action="store_true")
    send.set_defaults(func=send_message)

    receive = subparsers.add_parser("receive-messages", help="Read versioned mailbox messages for one recipient")
    receive.add_argument("run_dir")
    receive.add_argument("--worker-id")
    receive.add_argument("--recipient", type=parse_endpoint)
    receive.add_argument("--after-message-id")
    receive.add_argument("--round-id")
    receive.add_argument("--thread-id")
    receive.add_argument("--kind", choices=sorted(MESSAGE_KINDS))
    receive.set_defaults(func=receive_messages)

    message = subparsers.add_parser("append-message", help="Compatibility alias for send-message")
    message.add_argument("run_dir")
    message.add_argument("--message-id")
    message.add_argument("--round-id")
    message.add_argument("--thread-id")
    message.add_argument("--worker-id", required=True)
    message.add_argument("--role")
    message.add_argument("--scope")
    message.add_argument("--kind", required=True, choices=sorted(MESSAGE_KINDS))
    message.add_argument("--target-message-id")
    message.add_argument("--recipient", action="append", type=parse_endpoint)
    message.add_argument("--direction", choices=sorted(MESSAGE_DIRECTIONS))
    message.add_argument("--summary", required=True)
    message.add_argument("--body")
    message.add_argument("--evidence-ref", action="append")
    message.add_argument("--requires-response", action="store_true")
    message.set_defaults(func=append_message)

    acquire = subparsers.add_parser("acquire-lease", help="Acquire a file-scope write lease")
    acquire.add_argument("run_dir")
    acquire.add_argument("--lease-id")
    acquire.add_argument("--worker-id", required=True)
    acquire.add_argument("--scope", required=True, action="append")
    acquire.set_defaults(func=acquire_lease)

    release = subparsers.add_parser("release-lease", help="Release a file-scope write lease")
    release.add_argument("run_dir")
    release.add_argument("lease_id")
    release.set_defaults(func=release_lease)

    check = subparsers.add_parser("check", help="Validate a TeamExecutor run directory")
    check.add_argument("run_dir")
    check.set_defaults(func=check_run)

    launch_parser = subparsers.add_parser("launch", help="Launch tmux panes for registered workers")
    launch_parser.add_argument("run_dir")
    launch_parser.add_argument("--session")
    launch_parser.add_argument("--cwd")
    launch_parser.add_argument("--worker-command", action="append", type=parse_assignment)
    launch_parser.add_argument("--dry-run", action="store_true")
    launch_parser.set_defaults(func=launch)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
