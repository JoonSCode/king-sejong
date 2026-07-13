from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final, NewType

from delegation_run_model import (
    DelegationContractError,
    DelegationRun,
    JsonObject,
    JsonValue,
    Worker,
    WorkerId,
    WorkerStatus,
    now_utc,
    reserve_registered_workers,
)


WaveId = NewType("WaveId", str)
ReceiptId = NewType("ReceiptId", str)
WORKER_RECEIPT_FORMAT: Final = "sejong.delegation-worker-receipt/v0.1-draft"
FAN_IN_RECEIPT_FORMAT: Final = "sejong.delegation-fan-in-receipt/v0.1-draft"
EVIDENCE_AUTHORITY: Final = "evidence_only"
FAN_IN_AUTHORITY: Final = "orchestration_evidence_only"


class WaveStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TerminalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class TerminalReceiptRequest:
    receipt_id: ReceiptId
    wave_id: WaveId
    worker_id: WorkerId
    backend_worker_ref: str
    worker_contract_ref: str
    worker_output_ref: str
    terminal_status: TerminalStatus
    summary: str
    evidence_refs: tuple[str, ...]
    blocker: str | None


def _wave(run: DelegationRun, wave_id: WaveId) -> JsonObject:
    for wave in run.waves:
        if wave.get("wave_id") == wave_id:
            return wave
    raise DelegationContractError(f"unknown wave: {wave_id}")


def _worker(run: DelegationRun, worker_id: WorkerId) -> Worker:
    for worker in run.workers:
        if worker.worker_id == worker_id:
            return worker
    raise DelegationContractError(f"unknown worker: {worker_id}")


def _text_list(value: JsonValue, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise DelegationContractError(f"{label} must contain non-empty strings")
    return tuple(item for item in value if isinstance(item, str))


def _replace_wave(run: DelegationRun, updated: JsonObject) -> tuple[JsonObject, ...]:
    wave_id = updated["wave_id"]
    return tuple(updated if wave.get("wave_id") == wave_id else wave for wave in run.waves)


def _require_valid_persisted_state(run: DelegationRun) -> None:
    if failures := wave_failures(run):
        raise DelegationContractError(f"invalid persisted wave state: {'; '.join(failures)}")


def add_wave(
    run: DelegationRun,
    wave_id: WaveId,
    worker_ids: tuple[WorkerId, ...],
    dependencies: tuple[WaveId, ...],
) -> DelegationRun:
    _require_valid_persisted_state(run)
    if not wave_id or not worker_ids:
        raise DelegationContractError("wave_id and worker_ids must be non-empty")
    if any(wave.get("wave_id") == wave_id for wave in run.waves):
        raise DelegationContractError(f"wave already exists: {wave_id}")
    if len(set(worker_ids)) != len(worker_ids) or len(set(dependencies)) != len(dependencies):
        raise DelegationContractError("wave workers and dependencies must be unique")
    known_waves = {wave.get("wave_id") for wave in run.waves}
    unknown_dependencies = sorted(str(item) for item in dependencies if item not in known_waves)
    if unknown_dependencies:
        raise DelegationContractError(f"unknown wave dependencies: {unknown_dependencies}")
    assigned = {
        worker_id
        for wave in run.waves
        for worker_id in _text_list(wave.get("required_worker_ids"), "required_worker_ids")
    }
    for worker_id in worker_ids:
        worker = _worker(run, worker_id)
        if worker.status is not WorkerStatus.REGISTERED:
            raise DelegationContractError(f"wave worker is not registered: {worker_id}")
        if worker_id in assigned:
            raise DelegationContractError(f"worker already belongs to a wave: {worker_id}")
    if len(run.rounds_started) >= run.budget.max_rounds:
        raise DelegationContractError("max_rounds exceeded")
    wave: JsonObject = {
        "wave_id": wave_id,
        "ordinal": len(run.waves) + 1,
        "depends_on": list(dependencies),
        "required_worker_ids": list(worker_ids),
        "status": WaveStatus.PENDING.value,
        "opened_at": None,
        "closed_at": None,
        "fan_in_receipt_id": None,
    }
    return replace(
        run,
        waves=(*run.waves, wave),
        rounds_started=(*run.rounds_started, f"wave:{wave_id}"),
    )


def _passed_fan_in(run: DelegationRun, wave_id: str) -> bool:
    return any(
        receipt.get("receipt_type") == "fan_in"
        and receipt.get("wave_id") == wave_id
        and receipt.get("aggregate_status") == WaveStatus.PASSED.value
        for receipt in run.receipts
    )


def open_wave(run: DelegationRun, wave_id: WaveId) -> DelegationRun:
    _require_valid_persisted_state(run)
    wave = _wave(run, wave_id)
    if wave.get("status") != WaveStatus.PENDING.value:
        raise DelegationContractError(f"wave is not pending: {wave_id}")
    if any(item.get("status") == WaveStatus.ACTIVE.value for item in run.waves):
        raise DelegationContractError("another wave is already active")
    for dependency in _text_list(wave.get("depends_on"), "depends_on"):
        if not _passed_fan_in(run, dependency):
            raise DelegationContractError(f"dependency fan-in has not passed: {dependency}")
    required = tuple(WorkerId(item) for item in _text_list(wave.get("required_worker_ids"), "required_worker_ids"))
    launched = reserve_registered_workers(run, required)
    updated = dict(wave)
    updated["status"] = WaveStatus.ACTIVE.value
    updated["opened_at"] = now_utc()
    return replace(launched, waves=_replace_wave(launched, updated))


def record_terminal(run: DelegationRun, request: TerminalReceiptRequest) -> DelegationRun:
    _require_valid_persisted_state(run)
    wave = _wave(run, request.wave_id)
    if wave.get("status") != WaveStatus.ACTIVE.value:
        raise DelegationContractError(f"wave is not active: {request.wave_id}")
    required = _text_list(wave.get("required_worker_ids"), "required_worker_ids")
    if request.worker_id not in required:
        raise DelegationContractError(f"worker is not required by wave: {request.worker_id}")
    if any(receipt.get("receipt_id") == request.receipt_id for receipt in run.receipts):
        raise DelegationContractError(f"receipt already exists: {request.receipt_id}")
    if any(
        receipt.get("receipt_type") == "worker_terminal" and receipt.get("worker_id") == request.worker_id
        for receipt in run.receipts
    ):
        raise DelegationContractError(f"terminal receipt already exists: {request.worker_id}")
    worker = _worker(run, request.worker_id)
    if worker.status is not WorkerStatus.LAUNCHED:
        raise DelegationContractError(f"worker is not launched: {request.worker_id}")
    if request.terminal_status is TerminalStatus.COMPLETED and (
        not request.worker_output_ref or not request.evidence_refs
    ):
        raise DelegationContractError("completed receipt requires worker output and evidence")
    if request.terminal_status is TerminalStatus.COMPLETED and request.blocker is not None:
        raise DelegationContractError("completed receipt cannot carry blocker")
    if request.terminal_status is not TerminalStatus.COMPLETED and not request.blocker:
        raise DelegationContractError("non-success receipt requires blocker disposition")
    receipt: JsonObject = {
        "format": WORKER_RECEIPT_FORMAT,
        "receipt_type": "worker_terminal",
        "receipt_id": request.receipt_id,
        "run_id": run.run_id,
        "wave_id": request.wave_id,
        "worker_id": request.worker_id,
        "backend": worker.backend.value,
        "backend_worker_ref": request.backend_worker_ref,
        "worker_contract_ref": request.worker_contract_ref,
        "worker_output_ref": request.worker_output_ref,
        "terminal_status": request.terminal_status.value,
        "summary": request.summary,
        "evidence_refs": list(request.evidence_refs),
        "blocker": request.blocker,
        "authority": EVIDENCE_AUTHORITY,
        "created_at": now_utc(),
    }
    status = WorkerStatus(request.terminal_status.value)
    workers = tuple(replace(item, status=status) if item.worker_id == worker.worker_id else item for item in run.workers)
    return replace(run, workers=workers, receipts=(*run.receipts, receipt))


def fan_in(run: DelegationRun, wave_id: WaveId) -> tuple[DelegationRun, JsonObject]:
    _require_valid_persisted_state(run)
    wave = _wave(run, wave_id)
    if wave.get("status") != WaveStatus.ACTIVE.value:
        raise DelegationContractError(f"wave is not active: {wave_id}")
    required = _text_list(wave.get("required_worker_ids"), "required_worker_ids")
    receipts = [
        receipt
        for receipt in run.receipts
        if receipt.get("receipt_type") == "worker_terminal" and receipt.get("wave_id") == wave_id
    ]
    received = {str(receipt.get("worker_id")) for receipt in receipts}
    missing = sorted(set(required) - received)
    if missing:
        raise DelegationContractError(f"missing terminal receipts: {missing}")
    statuses = {receipt.get("terminal_status") for receipt in receipts}
    if statuses == {TerminalStatus.COMPLETED.value}:
        aggregate = WaveStatus.PASSED
    elif TerminalStatus.FAILED.value in statuses or TerminalStatus.TIMED_OUT.value in statuses:
        aggregate = WaveStatus.FAILED
    else:
        aggregate = WaveStatus.BLOCKED
    fan_in_id = ReceiptId(f"fan-in-{wave_id}")
    blocking = [
        str(receipt["receipt_id"])
        for receipt in receipts
        if receipt.get("terminal_status") != TerminalStatus.COMPLETED.value
    ]
    fan_in_receipt: JsonObject = {
        "format": FAN_IN_RECEIPT_FORMAT,
        "receipt_type": "fan_in",
        "receipt_id": fan_in_id,
        "run_id": run.run_id,
        "wave_id": wave_id,
        "required_worker_ids": list(required),
        "terminal_receipt_ids": [str(receipt["receipt_id"]) for receipt in receipts],
        "aggregate_status": aggregate.value,
        "blocking_receipt_ids": blocking,
        "authority": FAN_IN_AUTHORITY,
        "created_at": now_utc(),
    }
    updated = dict(wave)
    updated["status"] = aggregate.value
    updated["closed_at"] = now_utc()
    updated["fan_in_receipt_id"] = fan_in_id
    next_run = replace(run, waves=_replace_wave(run, updated), receipts=(*run.receipts, fan_in_receipt))
    return next_run, fan_in_receipt


def wave_failures(run: DelegationRun) -> tuple[str, ...]:
    from delegation_wave_validation import persisted_wave_failures

    return persisted_wave_failures(run)
