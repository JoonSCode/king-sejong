#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORMAT = "sejong.sillok-trace-event/v0.1-draft"
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
EVENT_KINDS = {
    "route_decision",
    "tool_call",
    "evidence_ref",
    "verification",
    "security_review",
    "handoff",
    "blocker",
}
RISK_FLAGS = {
    "private_data",
    "untrusted_content",
    "external_action",
    "credential_access",
    "network_access",
    "write_action",
}
LETHAL_TRIFECTA = {"private_data", "untrusted_content", "external_action"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sejong_root() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def default_trace_path(args: argparse.Namespace) -> Path:
    if args.trace:
        return Path(args.trace).expanduser()
    if not args.repo_id or not args.run_id:
        raise SystemExit("--trace or both --repo-id and --run-id are required")
    return sejong_root() / "runs" / args.repo_id / args.run_id / "sillok-record.jsonl"


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, sort_keys=True) + "\n")


def validate_event(event: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = (
        "format",
        "event_id",
        "run_id",
        "active_context_id",
        "created_at",
        "surface",
        "event_kind",
        "summary",
        "refs",
        "risk_flags",
        "human_approval_ref",
    )
    for field in required:
        if field not in event:
            failures.append(f"missing {field}")
    if event.get("format") != FORMAT:
        failures.append("unexpected format")
    if event.get("surface") not in SURFACES:
        failures.append(f"invalid surface: {event.get('surface')}")
    if event.get("event_kind") not in EVENT_KINDS:
        failures.append(f"invalid event_kind: {event.get('event_kind')}")
    if not isinstance(event.get("refs"), list):
        failures.append("refs must be a list")
    risk_flags = event.get("risk_flags")
    if not isinstance(risk_flags, list):
        failures.append("risk_flags must be a list")
        risk_flags = []
    invalid_flags = sorted(set(risk_flags) - RISK_FLAGS)
    if invalid_flags:
        failures.append(f"invalid risk_flags: {', '.join(invalid_flags)}")
    if LETHAL_TRIFECTA.issubset(set(risk_flags)) and not event.get("human_approval_ref"):
        failures.append("lethal trifecta risk requires human_approval_ref")
    return failures


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL at line {line_no}: {exc}") from exc
    return events


def append_event(args: argparse.Namespace) -> int:
    trace_path = default_trace_path(args)
    event = {
        "format": FORMAT,
        "event_id": args.event_id or f"event-{timestamp_id()}",
        "run_id": args.run_id,
        "active_context_id": args.active_context_id,
        "created_at": now_utc(),
        "surface": args.surface,
        "event_kind": args.event_kind,
        "summary": args.summary,
        "refs": args.ref or [],
        "risk_flags": args.risk_flag or [],
        "human_approval_ref": args.human_approval_ref,
    }
    failures = validate_event(event)
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    append_jsonl(trace_path, event)
    print(f"event appended: {trace_path}")
    return 0


def check_trace(args: argparse.Namespace) -> int:
    trace_path = Path(args.trace).expanduser()
    if not trace_path.exists():
        print(f"missing trace: {trace_path}", file=sys.stderr)
        return 1
    failures: list[str] = []
    for index, event in enumerate(read_events(trace_path), start=1):
        for failure in validate_event(event):
            failures.append(f"event {index}: {failure}")
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    print(f"sillok trace ok: {trace_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and check King Sejong Sillok trace events.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    append = subparsers.add_parser("append", help="Append one trace event.")
    append.add_argument("--trace")
    append.add_argument("--repo-id")
    append.add_argument("--run-id", required=True)
    append.add_argument("--active-context-id", required=True)
    append.add_argument("--event-id")
    append.add_argument("--surface", required=True, choices=sorted(SURFACES))
    append.add_argument("--event-kind", required=True, choices=sorted(EVENT_KINDS))
    append.add_argument("--summary", required=True)
    append.add_argument("--ref", action="append")
    append.add_argument("--risk-flag", action="append", choices=sorted(RISK_FLAGS))
    append.add_argument("--human-approval-ref")
    append.set_defaults(func=append_event)

    check = subparsers.add_parser("check", help="Validate a trace JSONL file.")
    check.add_argument("trace")
    check.set_defaults(func=check_trace)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
