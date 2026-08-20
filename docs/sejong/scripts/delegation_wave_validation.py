from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import assert_never

from delegation_cleanup import CleanupStatus, cleanup_required_worker_ids
from delegation_receipt_validation import (
    ReceiptType,
    ReceiptValidationContext,
    parse_receipt_type,
    receipt_failures,
)
from delegation_run_model import DelegationRun, JsonObject, Worker, WorkerStatus
from delegation_wave import (
    TerminalStatus,
    WaveStatus,
    _text_list,
)


@dataclass(frozen=True, slots=True)
class _RunIndex:
    workers: dict[str, Worker]
    waves: dict[str, JsonObject]
    required_by_wave: dict[str, tuple[str, ...]]
    wave_by_worker: dict[str, str]
    terminals_by_wave: dict[str, tuple[JsonObject, ...]]
    terminals_by_worker: dict[str, tuple[JsonObject, ...]]
    cleanups_by_wave: dict[str, tuple[JsonObject, ...]]
    cleanups_by_worker: dict[str, tuple[JsonObject, ...]]
    fan_ins_by_wave: dict[str, tuple[JsonObject, ...]]


def _unique(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def _build_index(run: DelegationRun) -> tuple[_RunIndex, list[str]]:
    failures: list[str] = []
    workers = {str(worker.worker_id): worker for worker in run.workers}
    waves: dict[str, JsonObject] = {}
    required_by_wave: dict[str, tuple[str, ...]] = {}
    wave_by_worker: dict[str, str] = {}
    known_waves: set[str] = set()
    for expected_ordinal, wave in enumerate(run.waves, start=1):
        wave_id = str(wave.get("wave_id") or "")
        waves[wave_id] = wave
        dependencies = _text_list(wave.get("depends_on"), f"wave {wave_id} depends_on")
        required = _text_list(wave.get("required_worker_ids"), f"wave {wave_id} workers")
        required_by_wave[wave_id] = required
        if wave.get("ordinal") != expected_ordinal:
            failures.append(f"wave ordinal mismatch: {wave_id}")
        if not _unique(dependencies) or not _unique(required) or not required:
            failures.append(f"wave dependencies and workers must be unique and workers non-empty: {wave_id}")
        if not set(dependencies).issubset(known_waves):
            failures.append(f"wave dependencies must reference lower ordinals: {wave_id}")
        if not set(required).issubset(workers):
            failures.append(f"wave references unknown workers: {wave_id}")
        for worker_id in required:
            if worker_id in wave_by_worker:
                failures.append(f"worker belongs to multiple waves: {wave_id}")
            else:
                wave_by_worker[worker_id] = wave_id
        known_waves.add(wave_id)
    terminals_by_wave: defaultdict[str, list[JsonObject]] = defaultdict(list)
    terminals_by_worker: defaultdict[str, list[JsonObject]] = defaultdict(list)
    cleanups_by_wave: defaultdict[str, list[JsonObject]] = defaultdict(list)
    cleanups_by_worker: defaultdict[str, list[JsonObject]] = defaultdict(list)
    fan_ins_by_wave: defaultdict[str, list[JsonObject]] = defaultdict(list)
    validation_context = ReceiptValidationContext(run.run_id, workers, required_by_wave)
    for receipt in run.receipts:
        failures.extend(receipt_failures(validation_context, receipt))
        match parse_receipt_type(receipt):
            case ReceiptType.WORKER_TERMINAL:
                terminals_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
                terminals_by_worker[str(receipt.get("worker_id") or "")].append(receipt)
            case ReceiptType.WORKER_CLEANUP:
                cleanups_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
                cleanups_by_worker[str(receipt.get("worker_id") or "")].append(receipt)
            case ReceiptType.FAN_IN:
                fan_ins_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
            case None:
                pass
            case unreachable:
                assert_never(unreachable)
    cleanup_receipts = [
        receipt
        for receipts in cleanups_by_worker.values()
        for receipt in receipts
    ]
    lease_ids = [str(receipt.get("resource_lease_id") or "") for receipt in cleanup_receipts]
    lease_refs = [str(receipt.get("resource_lease_ref") or "") for receipt in cleanup_receipts]
    resource_ids = [
        resource_id
        for receipt in cleanup_receipts
        for field in ("released_resource_ids", "preserved_resource_ids", "failed_resource_ids")
        for resource_id in _text_list(receipt.get(field), f"cleanup receipt resource field {field}")
    ]
    if len(lease_ids) != len(set(lease_ids)):
        failures.append("cleanup resource lease ids must be unique")
    if len(lease_refs) != len(set(lease_refs)):
        failures.append("cleanup resource lease refs must be unique")
    if len(resource_ids) != len(set(resource_ids)):
        failures.append("cleanup resource ids must be unique across receipts")
    return (
        _RunIndex(
            workers,
            waves,
            required_by_wave,
            wave_by_worker,
            {key: tuple(value) for key, value in terminals_by_wave.items()},
            {key: tuple(value) for key, value in terminals_by_worker.items()},
            {key: tuple(value) for key, value in cleanups_by_wave.items()},
            {key: tuple(value) for key, value in cleanups_by_worker.items()},
            {key: tuple(value) for key, value in fan_ins_by_wave.items()},
        ),
        failures,
    )


def _expected_aggregate(
    terminals: tuple[JsonObject, ...],
    cleanups: tuple[JsonObject, ...],
) -> str | None:
    statuses = {receipt.get("terminal_status") for receipt in terminals}
    cleanup_statuses = {receipt.get("cleanup_status") for receipt in cleanups}
    cleanup_required = bool(cleanup_required_worker_ids(terminals))
    supported = {status.value for status in TerminalStatus}
    supported_cleanup = {status.value for status in CleanupStatus}
    if not statuses or not statuses.issubset(supported) or not cleanup_statuses.issubset(supported_cleanup):
        return None
    cleanup_ready = not cleanup_required or cleanup_statuses == {CleanupStatus.RELEASED.value}
    if statuses == {TerminalStatus.COMPLETED.value} and cleanup_ready:
        return WaveStatus.PASSED.value
    if TerminalStatus.FAILED.value in statuses or TerminalStatus.TIMED_OUT.value in statuses:
        return WaveStatus.FAILED.value
    return WaveStatus.BLOCKED.value


def _wave_correlation_failures(index: _RunIndex, wave_id: str) -> list[str]:
    wave = index.waves[wave_id]
    required = index.required_by_wave[wave_id]
    terminals = index.terminals_by_wave.get(wave_id, ())
    cleanups = index.cleanups_by_wave.get(wave_id, ())
    fan_ins = index.fan_ins_by_wave.get(wave_id, ())
    failures: list[str] = []
    for worker_id in required:
        worker = index.workers.get(worker_id)
        if worker is None:
            continue
        receipt_count = len(index.terminals_by_worker.get(worker_id, ()))
        cleanup_count = len(index.cleanups_by_worker.get(worker_id, ()))
        is_terminal = worker.status in {
            WorkerStatus.COMPLETED,
            WorkerStatus.FAILED,
            WorkerStatus.TIMED_OUT,
            WorkerStatus.BLOCKED,
        }
        if is_terminal and receipt_count != 1:
            failures.append(f"terminal wave worker must have exactly one receipt: {worker_id}")
        if not is_terminal and receipt_count:
            failures.append(f"non-terminal wave worker cannot have terminal receipt: {worker_id}")
        if cleanup_count > 1 or (cleanup_count and receipt_count != 1):
            failures.append(f"cleanup receipt requires exactly one terminal receipt: {worker_id}")
        if cleanup_count == 1 and receipt_count == 1:
            cleanup = index.cleanups_by_worker[worker_id][0]
            terminal = index.terminals_by_worker[worker_id][0]
            if cleanup.get("wave_id") != terminal.get("wave_id"):
                failures.append(f"cleanup and terminal receipt wave mismatch: {worker_id}")
            if cleanup.get("backend_worker_ref") != terminal.get("backend_worker_ref"):
                failures.append(f"cleanup and terminal backend worker mismatch: {worker_id}")
    status = wave.get("status")
    if status in {WaveStatus.PENDING.value, WaveStatus.ACTIVE.value}:
        if wave.get("fan_in_receipt_id") is not None or fan_ins:
            failures.append(f"pending or active wave cannot carry fan-in: {wave_id}")
        return failures
    if status not in {WaveStatus.PASSED.value, WaveStatus.FAILED.value, WaveStatus.BLOCKED.value}:
        failures.append(f"wave has unsupported status: {wave_id}")
        return failures
    if len(fan_ins) != 1:
        failures.append(f"closed wave must reference exactly one fan-in: {wave_id}")
        return failures
    fan_in = fan_ins[0]
    if wave.get("fan_in_receipt_id") != fan_in.get("receipt_id"):
        failures.append(f"closed wave fan-in reference mismatch: {wave_id}")
    required_claim = _text_list(fan_in.get("required_worker_ids"), f"fan-in {wave_id} required_worker_ids")
    terminal_claim = _text_list(fan_in.get("terminal_receipt_ids"), f"fan-in {wave_id} terminal_receipt_ids")
    cleanup_claim = _text_list(fan_in.get("cleanup_receipt_ids"), f"fan-in {wave_id} cleanup_receipt_ids")
    blocking_claim = _text_list(fan_in.get("blocking_receipt_ids"), f"fan-in {wave_id} blocking_receipt_ids")
    terminal_ids = tuple(str(receipt.get("receipt_id") or "") for receipt in terminals)
    terminal_workers = tuple(str(receipt.get("worker_id") or "") for receipt in terminals)
    cleanup_required_workers = tuple(cleanup_required_worker_ids(terminals))
    cleanup_ids = tuple(str(receipt.get("receipt_id") or "") for receipt in cleanups)
    cleanup_workers = tuple(str(receipt.get("worker_id") or "") for receipt in cleanups)
    blocking_ids = tuple(
        str(receipt.get("receipt_id") or "")
        for receipt in terminals
        if receipt.get("terminal_status") != TerminalStatus.COMPLETED.value
    ) + tuple(
        str(receipt.get("receipt_id") or "")
        for receipt in cleanups
        if receipt.get("cleanup_status") != CleanupStatus.RELEASED.value
    )
    if not _unique(required_claim) or set(required_claim) != set(required):
        failures.append(f"fan-in required workers do not exactly cover wave: {wave_id}")
    if not _unique(terminal_claim) or set(terminal_claim) != set(terminal_ids):
        failures.append(f"fan-in terminal receipts do not exactly cover wave: {wave_id}")
    if not _unique(terminal_workers) or set(terminal_workers) != set(required):
        failures.append(f"terminal receipts do not exactly cover wave workers: {wave_id}")
    if not _unique(cleanup_claim) or set(cleanup_claim) != set(cleanup_ids):
        failures.append(f"fan-in cleanup receipts do not exactly cover wave: {wave_id}")
    if not _unique(cleanup_workers) or set(cleanup_workers) != set(cleanup_required_workers):
        failures.append(f"cleanup receipts do not exactly cover wave workers: {wave_id}")
    aggregate = _expected_aggregate(terminals, cleanups)
    if aggregate is None or fan_in.get("aggregate_status") != aggregate or status != aggregate:
        failures.append(f"fan-in aggregate_status does not match terminal and cleanup statuses: {wave_id}")
    if not _unique(blocking_claim) or set(blocking_claim) != set(blocking_ids):
        failures.append(f"fan-in blocking receipts do not match terminal and cleanup statuses: {wave_id}")
    return failures


def persisted_wave_failures(run: DelegationRun) -> tuple[str, ...]:
    failures: list[str] = []
    wave_ids = [str(wave.get("wave_id") or "") for wave in run.waves]
    receipt_ids = [str(receipt.get("receipt_id") or "") for receipt in run.receipts]
    if len(wave_ids) != len(set(wave_ids)) or "" in wave_ids:
        failures.append("wave ids must be unique non-empty strings")
    if len(receipt_ids) != len(set(receipt_ids)) or "" in receipt_ids:
        failures.append("receipt ids must be unique non-empty strings")
    if len(run.rounds_started) > run.budget.max_rounds:
        failures.append("max_rounds exceeded")
    index, index_failures = _build_index(run)
    failures.extend(index_failures)
    for wave_id in index.waves:
        failures.extend(_wave_correlation_failures(index, wave_id))
    for wave_id in index.fan_ins_by_wave:
        if wave_id not in index.waves:
            failures.append(f"fan-in receipt references unknown wave: {wave_id}")
    return tuple(failures)
