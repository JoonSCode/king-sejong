from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from codex_process_contract import CodexProcessRequest, build_codex_process
from codex_process_runtime import CodexProcess, ProcessResult, ProcessStatus
from codex_subprocess_adapter import SubprocessCodexProcess
from codex_ticket_binding import DelegationBinding, validate_delegation_binding
from delegation_run import record_terminal_receipt
from delegation_run_model import WorkerId
from delegation_wave import ReceiptId, TerminalReceiptRequest, TerminalStatus, WaveId
from discord_contract_types import ControlContractError, TicketIntent
from discord_target_registry import ResolvedTarget


__all__ = ["ProcessResult", "ProcessStatus", "SubprocessCodexProcess"]


class TicketRunStatus(StrEnum):
    DRY_RUN = "dry_run"
    PROCESS_COMPLETED = "process_completed"
    PROCESS_FAILED = "process_failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TicketRunSpec:
    ticket: TicketIntent
    target: ResolvedTarget
    workspace: Path
    sejong_home: Path
    delegation: DelegationBinding | None

    @property
    def run_dir(self) -> Path:
        return self.sejong_home / "runs" / "discord" / self.ticket.ticket_id

    @property
    def cancellation_path(self) -> Path:
        return self.sejong_home / "state" / "discord" / "cancellations" / self.ticket.ticket_id


@dataclass(frozen=True, slots=True)
class TicketRunResult:
    status: TicketRunStatus
    receipt_path: Path


@dataclass(frozen=True, slots=True)
class TicketRunner:
    process: CodexProcess

    def run(self, spec: TicketRunSpec) -> TicketRunResult:
        request = build_codex_process(spec.ticket, spec.target, spec.workspace)
        spec.run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (spec.run_dir / "ticket-run-receipt.json").exists():
            raise ControlContractError("immutable_receipt_exists", "ticket process receipt is already sealed")
        if spec.cancellation_path.exists():
            validate_delegation_binding(spec)
            cancelled = ProcessResult(ProcessStatus.CANCELLED, None, "", "", False)
            receipt_path = _write_receipt(spec, request, TicketRunStatus.CANCELLED, cancelled)
            if spec.delegation is not None:
                _record_terminal(spec, receipt_path, ProcessStatus.CANCELLED)
            return TicketRunResult(TicketRunStatus.CANCELLED, receipt_path)
        if spec.ticket.dry_run:
            receipt_path = _write_receipt(spec, request, TicketRunStatus.DRY_RUN, None)
            return TicketRunResult(TicketRunStatus.DRY_RUN, receipt_path)
        validate_delegation_binding(spec)
        result = _bound_result(
            self.process.run(request, spec.cancellation_path),
            request.output_limit_bytes,
        )
        receipt_path = _write_receipt(spec, request, _ticket_status(result.status), result)
        if spec.delegation is not None:
            _record_terminal(spec, receipt_path, result.status)
        return TicketRunResult(_ticket_status(result.status), receipt_path)


def _ticket_status(status: ProcessStatus) -> TicketRunStatus:
    match status:
        case ProcessStatus.COMPLETED:
            return TicketRunStatus.PROCESS_COMPLETED
        case ProcessStatus.FAILED:
            return TicketRunStatus.PROCESS_FAILED
        case ProcessStatus.TIMED_OUT:
            return TicketRunStatus.TIMED_OUT
        case ProcessStatus.CANCELLED:
            return TicketRunStatus.CANCELLED


def _bound_result(result: ProcessResult, limit: int) -> ProcessResult:
    stdout_bytes = result.stdout.encode()
    stderr_bytes = result.stderr.encode()
    stdout = stdout_bytes[:limit].decode(errors="ignore")
    remaining = max(0, limit - len(stdout.encode()))
    stderr = stderr_bytes[:remaining].decode(errors="ignore")
    return ProcessResult(
        status=result.status,
        exit_code=result.exit_code,
        stdout=stdout,
        stderr=stderr,
        truncated=result.truncated or len(stdout_bytes) + len(stderr_bytes) > limit,
    )


def _terminal_disposition(status: ProcessStatus) -> tuple[TerminalStatus, str | None]:
    match status:
        case ProcessStatus.COMPLETED:
            return TerminalStatus.COMPLETED, None
        case ProcessStatus.FAILED:
            return TerminalStatus.FAILED, "Codex ticket process failed"
        case ProcessStatus.TIMED_OUT:
            return TerminalStatus.TIMED_OUT, "Codex ticket process timed out"
        case ProcessStatus.CANCELLED:
            return TerminalStatus.BLOCKED, "Codex ticket process was cancelled"
        case unreachable:
            assert_never(unreachable)


def _record_terminal(spec: TicketRunSpec, receipt_path: Path, status: ProcessStatus) -> None:
    binding = spec.delegation
    if binding is None:
        return
    terminal_status, blocker = _terminal_disposition(status)
    record_terminal_receipt(
        binding.delegation_run_path,
        TerminalReceiptRequest(
            receipt_id=ReceiptId(f"codex-ticket-{spec.ticket.ticket_id}"),
            wave_id=WaveId(binding.wave_id),
            worker_id=WorkerId(binding.worker_id),
            backend_worker_ref=f"codex-process://discord/{spec.ticket.ticket_id}",
            worker_contract_ref=binding.worker_contract_ref,
            worker_output_ref=str(receipt_path),
            terminal_status=terminal_status,
            summary=f"Codex ticket process {status.value}; evidence awaits Core fan-in and review",
            evidence_refs=(str(receipt_path),),
            blocker=blocker,
        ),
    )


def _write_receipt(
    spec: TicketRunSpec,
    request: CodexProcessRequest,
    status: TicketRunStatus,
    result: ProcessResult | None,
) -> Path:
    payload = {
        "format": "sejong.codex-ticket-run-receipt/v0.1-draft",
        "ticket_id": spec.ticket.ticket_id,
        "status": status.value,
        "completion_authority": "evidence_only",
        "completion_eligible": False,
        "model": request.model,
        "sandbox": spec.ticket.sandbox.value,
        "prompt_sha256": hashlib.sha256(request.stdin_text.encode()).hexdigest(),
        "process": {
            "argv": list(request.argv),
            "cwd": str(request.cwd),
            "timeout_seconds": request.timeout_seconds,
            "output_limit_bytes": request.output_limit_bytes,
        },
        "result": None
        if result is None
        else {
            "status": result.status.value,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "truncated": result.truncated,
        },
    }
    receipt_path = spec.run_dir / "ticket-run-receipt.json"
    temporary = receipt_path.with_name(f".{receipt_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    try:
        os.link(temporary, receipt_path)
    except FileExistsError as exc:
        raise ControlContractError("immutable_receipt_exists", "ticket process receipt is already sealed") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return receipt_path
