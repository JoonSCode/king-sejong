#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from delegation_cleanup import (
    CleanupCapability,
    CleanupReceiptId,
    CleanupReceiptRequest,
    CleanupStatus,
    record_cleanup_receipt,
)
from delegation_run import record_terminal_receipt
from delegation_run_model import Backend, DelegationContractError, WorkerId, load_run
from delegation_wave import ReceiptId, TerminalReceiptRequest, TerminalStatus, WaveId
from worker_resource_model import (
    CleanupCapability as LeaseCapability,
    LeaseStatus,
    WorkerResourceLease,
    load_lease,
)


@dataclass(frozen=True, slots=True)
class NativeTerminalResult:
    receipt_id: str
    wave_id: str
    worker_id: str
    agent_thread_id: str
    worker_contract_ref: str
    worker_output_ref: str
    terminal_status: str
    summary: str
    evidence_refs: tuple[str, ...]
    blocker: str | None = None


@dataclass(frozen=True, slots=True)
class NativeCleanupResult:
    receipt_id: str
    agent_thread_id: str
    worker_resource_lease: Path


class NativeCommand(StrEnum):
    RECORD_TERMINAL = "record-terminal"
    RECORD_CLEANUP = "record-cleanup"


def _require_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise DelegationContractError(f"{field_name} must be a non-empty string")
    return value


def record_native_terminal(path: Path, result: NativeTerminalResult) -> None:
    run = load_run(path)
    worker_id = WorkerId(_require_text(result.worker_id, "worker_id"))
    worker = next((item for item in run.workers if item.worker_id == worker_id), None)
    if worker is None:
        raise DelegationContractError(f"unknown worker: {worker_id}")
    if worker.backend is not Backend.NATIVE:
        raise DelegationContractError(f"worker backend must be native: {worker_id}")
    agent_thread_id = _require_text(result.agent_thread_id, "agent_thread_id")
    record_terminal_receipt(
        path,
        TerminalReceiptRequest(
            receipt_id=ReceiptId(_require_text(result.receipt_id, "receipt_id")),
            wave_id=WaveId(_require_text(result.wave_id, "wave_id")),
            worker_id=worker_id,
            backend_worker_ref=f"codex-thread://{agent_thread_id}",
            worker_contract_ref=_require_text(
                result.worker_contract_ref, "worker_contract_ref"
            ),
            worker_output_ref=_require_text(
                result.worker_output_ref, "worker_output_ref"
            ),
            terminal_status=TerminalStatus(result.terminal_status),
            summary=_require_text(result.summary, "summary"),
            evidence_refs=tuple(
                _require_text(reference, "evidence_ref")
                for reference in result.evidence_refs
            ),
            blocker=result.blocker,
        ),
    )


def _cleanup_status(lease: WorkerResourceLease) -> CleanupStatus:
    match lease.status:
        case LeaseStatus.RELEASED:
            return CleanupStatus.RELEASED
        case LeaseStatus.PRESERVED:
            return CleanupStatus.PRESERVED
        case LeaseStatus.FAILED:
            return CleanupStatus.FAILED
        case LeaseStatus.ORPHANED if lease.cleanup_capability is LeaseCapability.AUDIT_ONLY:
            return CleanupStatus.AUDIT_ONLY
        case LeaseStatus.ORPHANED:
            return CleanupStatus.FAILED
        case LeaseStatus.ACTIVE | LeaseStatus.RELEASING:
            raise DelegationContractError("worker resource lease is not terminal")
        case unreachable:
            assert_never(unreachable)


def record_native_cleanup(path: Path, result: NativeCleanupResult) -> None:
    run = load_run(path)
    lease = load_lease(result.worker_resource_lease)
    worker_id = WorkerId(lease.owner.worker_id)
    worker = next((item for item in run.workers if item.worker_id == worker_id), None)
    if worker is None or worker.backend is not Backend.NATIVE:
        raise DelegationContractError(f"worker backend must be native: {worker_id}")
    backend_worker_ref = f"codex-thread://{_require_text(result.agent_thread_id, 'agent_thread_id')}"
    if lease.owner.run_id != run.run_id or lease.owner.backend != Backend.NATIVE.value:
        raise DelegationContractError("worker resource lease owner does not match delegation run")
    if lease.owner.backend_worker_ref != backend_worker_ref:
        raise DelegationContractError("worker resource lease does not match native agent thread")
    status = _cleanup_status(lease)
    resource_ids = tuple(resource.resource_id for resource in lease.resources)
    record_cleanup_receipt(
        path,
        CleanupReceiptRequest(
            receipt_id=CleanupReceiptId(_require_text(result.receipt_id, "receipt_id")),
            wave_id=lease.owner.wave_id,
            worker_id=worker_id,
            backend_worker_ref=backend_worker_ref,
            resource_lease_ref=str(result.worker_resource_lease.resolve()),
            resource_lease_id=lease.lease_id,
            cleanup_capability=CleanupCapability(lease.cleanup_capability.value),
            cleanup_status=status,
            released_resource_ids=resource_ids if status is CleanupStatus.RELEASED else (),
            preserved_resource_ids=resource_ids if status is CleanupStatus.PRESERVED else (),
            failed_resource_ids=resource_ids if status in {CleanupStatus.FAILED, CleanupStatus.AUDIT_ONLY} else (),
            proof_refs=lease.proof_refs,
            blocker=lease.blocker,
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Project host-native Codex terminal results into a Sejong DelegationRun receipt."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    terminal = commands.add_parser(
        "record-terminal",
        help="Record one native Codex agent terminal result",
    )
    terminal.add_argument("path", type=Path)
    terminal.add_argument("--receipt-id", required=True)
    terminal.add_argument("--wave-id", required=True)
    terminal.add_argument("--worker-id", required=True)
    terminal.add_argument("--agent-thread-id", required=True)
    terminal.add_argument("--worker-contract-ref", required=True)
    terminal.add_argument("--worker-output-ref", required=True)
    terminal.add_argument(
        "--status",
        required=True,
        choices=[status.value for status in TerminalStatus],
    )
    terminal.add_argument("--summary", required=True)
    terminal.add_argument("--evidence-ref", required=True, action="append")
    terminal.add_argument("--blocker")
    cleanup = commands.add_parser(
        "record-cleanup",
        help="Record host-native cleanup evidence from a terminal worker resource lease",
    )
    cleanup.add_argument("path", type=Path)
    cleanup.add_argument("--receipt-id", required=True)
    cleanup.add_argument("--agent-thread-id", required=True)
    cleanup.add_argument("--worker-resource-lease", required=True, type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> None:
    match NativeCommand(args.command):
        case NativeCommand.RECORD_TERMINAL:
            record_native_terminal(
                args.path,
                NativeTerminalResult(
                    receipt_id=args.receipt_id,
                    wave_id=args.wave_id,
                    worker_id=args.worker_id,
                    agent_thread_id=args.agent_thread_id,
                    worker_contract_ref=args.worker_contract_ref,
                    worker_output_ref=args.worker_output_ref,
                    terminal_status=args.status,
                    summary=args.summary,
                    evidence_refs=tuple(args.evidence_ref),
                    blocker=args.blocker,
                ),
            )
        case NativeCommand.RECORD_CLEANUP:
            record_native_cleanup(
                args.path,
                NativeCleanupResult(
                    receipt_id=args.receipt_id,
                    agent_thread_id=args.agent_thread_id,
                    worker_resource_lease=args.worker_resource_lease,
                ),
            )
        case unreachable:
            assert_never(unreachable)


def main() -> int:
    args = _build_parser().parse_args()
    try:
        _dispatch(args)
    except (DelegationContractError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"ok: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
