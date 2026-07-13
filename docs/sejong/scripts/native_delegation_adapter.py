#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from delegation_run import record_terminal_receipt
from delegation_run_model import Backend, DelegationContractError, WorkerId, load_run
from delegation_wave import ReceiptId, TerminalReceiptRequest, TerminalStatus, WaveId


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
    return parser


def _dispatch(args: argparse.Namespace) -> None:
    if args.command != "record-terminal":
        raise DelegationContractError(f"unsupported command: {args.command}")
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
