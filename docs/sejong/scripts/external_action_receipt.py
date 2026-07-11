#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run external_action_receipt.py --help
# 3. Or make executable and run:
#      chmod +x external_action_receipt.py && ./external_action_receipt.py --help
# ─────────────────

from __future__ import annotations

import argparse
import hashlib
import os
import socket
import sys
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Final, assert_never

from external_action_contract import (
    ActionIntent,
    ActionStatus,
    AuthorizationRequest,
    ReceiptError,
    RecordRequest,
    authorize,
    parse_timestamp,
    record,
)
from external_action_storage import load_approval_record, load_ledger, write_ledger
from sejong_runtime_lock import RuntimeLockClass, RuntimeLockRequest, RuntimeLockTimeout, acquire_runtime_lock


RECORD_STATUSES: Final = (
    ActionStatus.DISPATCHED,
    ActionStatus.COMPLETED,
    ActionStatus.FAILED,
    ActionStatus.CANCELLED,
)


class Command(StrEnum):
    AUTHORIZE = "authorize"
    RECORD = "record"
    CHECK = "check"


def lock_request(path: Path, operation: str) -> RuntimeLockRequest:
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:24]
    return RuntimeLockRequest(
        sejong_home=None,
        lock_name=f"external-action-{digest}",
        lock_class=RuntimeLockClass.ARTIFACT_REF,
        owner_session_id=f"external-action-{os.getpid()}",
        owner_device_id=socket.gethostname(),
        operation=operation,
    )


def authorize_command(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser()
    input_sha = hashlib.sha256(Path(args.input_file).expanduser().read_bytes()).hexdigest()
    intent = ActionIntent(args.action_id, args.action_name, args.target_description, input_sha, args.idempotency_key)
    request = AuthorizationRequest(
        args.run_id,
        intent,
        load_approval_record(Path(args.approval_record)),
        datetime.now(timezone.utc),
    )
    lock = acquire_runtime_lock(lock_request(ledger_path, "authorize external action"))
    try:
        ledger = load_ledger(ledger_path) if ledger_path.exists() else None
        write_ledger(ledger_path, authorize(ledger, request))
    finally:
        lock.release()
    print(f"external action authorized: {args.action_id}")
    return 0


def record_command(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser()
    request = RecordRequest(
        args.action_id,
        ActionStatus(args.status),
        parse_timestamp(args.at, "at"),
        tuple(args.evidence_ref or ()),
    )
    lock = acquire_runtime_lock(lock_request(ledger_path, "record external action state"))
    try:
        write_ledger(ledger_path, record(load_ledger(ledger_path), request))
    finally:
        lock.release()
    print(f"external action recorded: {args.action_id} -> {args.status}")
    return 0


def check_command(path: str) -> int:
    ledger = load_ledger(Path(path).expanduser())
    print(f"external action receipts ok: run_id={ledger.run_id} receipts={len(ledger.receipts)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record approval-bound, idempotent external-action receipts without executing the action."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve = subparsers.add_parser("authorize", help="Record approval and hashes before an external action.")
    approve.add_argument("--ledger", required=True)
    approve.add_argument("--run-id", required=True)
    approve.add_argument("--action-id", required=True)
    approve.add_argument("--action-name", required=True)
    approve.add_argument("--target-description", required=True)
    approve.add_argument("--input-file", required=True)
    approve.add_argument("--idempotency-key", required=True)
    approve.add_argument("--approval-record", required=True)

    transition = subparsers.add_parser("record", help="Record dispatch or terminal state after authorization.")
    transition.add_argument("--ledger", required=True)
    transition.add_argument("--action-id", required=True)
    transition.add_argument("--status", required=True, choices=[status.value for status in RECORD_STATUSES])
    transition.add_argument("--at", required=True)
    transition.add_argument("--evidence-ref", action="append")

    check = subparsers.add_parser("check", help="Validate a receipt ledger and its invariants.")
    check.add_argument("ledger")
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        command = Command(args.command)
    except ValueError as exc:
        raise ReceiptError(f"unknown command: {args.command}") from exc
    match command:
        case Command.AUTHORIZE:
            return authorize_command(args)
        case Command.RECORD:
            return record_command(args)
        case Command.CHECK:
            return check_command(args.ledger)
        case unreachable:
            assert_never(unreachable)


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except (ReceiptError, FileNotFoundError, PermissionError, RuntimeLockTimeout) as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
