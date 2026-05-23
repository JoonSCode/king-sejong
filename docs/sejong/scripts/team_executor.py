#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEAM_FORMAT = "sejong.team/v0.1-draft"
ROUNDS_FORMAT = "sejong.team-rounds/v0.1-draft"
LEASES_FORMAT = "sejong.team-leases/v0.1-draft"
WORKER_FORMAT = "sejong.team-worker/v0.1-draft"

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


def add_worker_record(run_dir: Path, worker: dict[str, str], command: str | None = None) -> None:
    team = load_team(run_dir)
    if worker["worker_id"] in worker_ids(team):
        raise SystemExit(f"worker already exists: {worker['worker_id']}")

    record: dict[str, Any] = {
        "worker_id": worker["worker_id"],
        "role": worker["role"],
        "scope": worker["scope"],
        "allowed_message_kinds": sorted(MESSAGE_KINDS),
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
            "worker_id": worker["worker_id"],
            "role": worker["role"],
            "scope": worker["scope"],
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
    write_json(
        team_path(run_dir),
        {
            "format": TEAM_FORMAT,
            "run_id": run_id,
            "created_at": now_utc(),
            "repo_root": str(repo_root),
            "brief_path": "brief.md",
            "workers": [],
        },
    )
    write_json(rounds_path(run_dir), {"format": ROUNDS_FORMAT, "run_id": run_id, "rounds": []})
    write_json(leases_path(run_dir), {"format": LEASES_FORMAT, "run_id": run_id, "leases": []})
    mailbox_path(run_dir).write_text("", encoding="utf-8")

    commands = dict(args.command or [])
    for worker in args.worker or []:
        add_worker_record(run_dir, worker, commands.get(worker["worker_id"]))

    print(str(run_dir))
    return 0


def add_worker(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    add_worker_record(run_dir, args.worker, args.command)
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


def append_message(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    if args.worker_id not in worker_ids(team):
        raise SystemExit(f"unknown worker: {args.worker_id}")
    if args.kind not in MESSAGE_KINDS:
        raise SystemExit(f"unsupported message kind: {args.kind}")

    round_id = args.round_id or current_open_round(run_dir)
    message_id = args.message_id or f"{round_id}-{args.worker_id}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    message = {
        "message_id": message_id,
        "run_id": team["run_id"],
        "round_id": round_id,
        "worker_id": args.worker_id,
        "role": args.role,
        "scope": args.scope,
        "kind": args.kind,
        "target_message_id": args.target_message_id,
        "summary": args.summary,
        "evidence_refs": args.evidence_ref or [],
        "created_at": now_utc(),
    }
    append_jsonl(mailbox_path(run_dir), message)
    print(f"message appended: {message_id}")
    return 0


def acquire_lease(args: argparse.Namespace) -> int:
    run_dir = require_run_dir(Path(args.run_dir))
    team = load_team(run_dir)
    if args.worker_id not in worker_ids(team):
        raise SystemExit(f"unknown worker: {args.worker_id}")
    leases = load_json(leases_path(run_dir))
    active = [lease for lease in leases.get("leases", []) if lease.get("status") == "active"]
    requested = set(args.scope)
    for lease in active:
        overlap = requested.intersection(set(lease.get("scopes", [])))
        if overlap and lease.get("worker_id") != args.worker_id:
            raise SystemExit(f"lease conflict on {sorted(overlap)} with {lease.get('worker_id')}")

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
    if ".omx" in json.dumps(team):
        failures.append("team.json references .omx state")

    seen_messages: set[str] = set()
    for message in read_mailbox(run_dir):
        if message.get("kind") not in MESSAGE_KINDS:
            failures.append(f"unsupported mailbox kind: {message.get('kind')}")
        message_id = message.get("message_id")
        if not message_id:
            failures.append("mailbox message missing message_id")
        elif message_id in seen_messages:
            failures.append(f"duplicate message_id: {message_id}")
        else:
            target = message.get("target_message_id")
            if target and target not in seen_messages:
                failures.append(f"target_message_id not found before reply: {target}")
            seen_messages.add(message_id)
        if ".omx" in json.dumps(message):
            failures.append(f"mailbox message references .omx state: {message_id}")

    leases = load_json(leases_path(run_dir))
    active: dict[str, str] = {}
    for lease in leases.get("leases", []):
        if lease.get("status") != "active":
            continue
        for scope in lease.get("scopes", []):
            owner = active.get(scope)
            if owner and owner != lease.get("worker_id"):
                failures.append(f"active lease conflict on {scope}: {owner} and {lease.get('worker_id')}")
            active[scope] = lease.get("worker_id", "")

    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    print(f"team run ok: {run_dir}")
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
        worker_env = f"SEJONG_TEAM_RUN={run_dir} SEJONG_TEAM_WORKER={worker_id} "
        shell_command = worker_env + command
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
    init.add_argument("--worker", action="append", type=parse_worker)
    init.add_argument("--command", action="append", type=parse_assignment)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=init_run)

    worker = subparsers.add_parser("add-worker", help="Register a worker in an existing run")
    worker.add_argument("run_dir")
    worker.add_argument("worker", type=parse_worker)
    worker.add_argument("--command")
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

    message = subparsers.add_parser("append-message", help="Append one mailbox message")
    message.add_argument("run_dir")
    message.add_argument("--message-id")
    message.add_argument("--round-id")
    message.add_argument("--worker-id", required=True)
    message.add_argument("--role", required=True)
    message.add_argument("--scope", required=True)
    message.add_argument("--kind", required=True, choices=sorted(MESSAGE_KINDS))
    message.add_argument("--target-message-id")
    message.add_argument("--summary", required=True)
    message.add_argument("--evidence-ref", action="append")
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
