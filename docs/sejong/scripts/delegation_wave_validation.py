from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from delegation_run_model import DelegationRun, JsonObject, JsonValue, Worker, WorkerStatus
from delegation_wave import (
    CLEANUP_CAPABILITY,
    CLEANUP_EVIDENCE_AUTHORITY,
    EVIDENCE_AUTHORITY,
    FAN_IN_AUTHORITY,
    FAN_IN_RECEIPT_FORMAT,
    WORKER_CLEANUP_RECEIPT_FORMAT,
    WORKER_RECEIPT_FORMAT,
    CleanupStatus,
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


def _is_text(value: JsonValue) -> bool:
    return isinstance(value, str) and bool(value)


def _unique(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def _receipt_boundary_failures(receipt: JsonObject, *, fan_in: bool) -> list[str]:
    expected_format = FAN_IN_RECEIPT_FORMAT if fan_in else WORKER_RECEIPT_FORMAT
    expected_authority = FAN_IN_AUTHORITY if fan_in else EVIDENCE_AUTHORITY
    receipt_id = str(receipt.get("receipt_id") or "")
    failures: list[str] = []
    if receipt.get("format") != expected_format:
        failures.append(f"receipt has unexpected format: {receipt_id}")
    if receipt.get("authority") != expected_authority:
        failures.append(f"receipt has unexpected authority: {receipt_id}")
    if not _is_text(receipt.get("created_at")):
        failures.append(f"receipt created_at must be non-empty: {receipt_id}")
    return failures


def _terminal_failures(run: DelegationRun, index: _RunIndex, receipt: JsonObject) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    wave_id = str(receipt.get("wave_id") or "")
    worker_id = str(receipt.get("worker_id") or "")
    failures = _receipt_boundary_failures(receipt, fan_in=False)
    if receipt.get("run_id") != run.run_id:
        failures.append(f"terminal receipt run_id mismatch: {receipt_id}")
    worker = index.workers.get(worker_id)
    if worker is None:
        failures.append(f"terminal receipt references unknown worker: {receipt_id}")
    elif receipt.get("backend") != worker.backend.value:
        failures.append(f"terminal receipt backend mismatch: {receipt_id}")
    required = index.required_by_wave.get(wave_id)
    if required is None:
        failures.append(f"terminal receipt references unknown wave: {receipt_id}")
    elif worker_id not in required:
        failures.append(f"terminal receipt worker is not required by wave: {receipt_id}")
    try:
        status = TerminalStatus(str(receipt.get("terminal_status") or ""))
    except ValueError:
        failures.append(f"terminal receipt has unsupported status: {receipt_id}")
        status = None
    if worker is not None and status is not None and worker.status.value != status.value:
        failures.append(f"terminal worker state does not match receipt: {worker_id}")
    for field in ("backend_worker_ref", "worker_contract_ref", "worker_output_ref", "summary"):
        if not _is_text(receipt.get(field)):
            failures.append(f"terminal receipt {field} must be non-empty: {receipt_id}")
    evidence_refs = _text_list(receipt.get("evidence_refs"), f"terminal receipt {receipt_id} evidence_refs")
    if not _unique(evidence_refs):
        failures.append(f"terminal receipt evidence_refs must be unique: {receipt_id}")
    blocker = receipt.get("blocker")
    if blocker is not None and not _is_text(blocker):
        failures.append(f"terminal receipt blocker must be non-empty or null: {receipt_id}")
    if status is TerminalStatus.COMPLETED and not evidence_refs:
        failures.append(f"completed terminal receipt requires evidence: {receipt_id}")
    if status is TerminalStatus.COMPLETED and blocker is not None:
        failures.append(f"completed terminal receipt cannot carry blocker: {receipt_id}")
    if status is not None and status is not TerminalStatus.COMPLETED and not _is_text(blocker):
        failures.append(f"non-success terminal receipt requires blocker: {receipt_id}")
    return failures


def _cleanup_failures(run: DelegationRun, index: _RunIndex, receipt: JsonObject) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    wave_id = str(receipt.get("wave_id") or "")
    worker_id = str(receipt.get("worker_id") or "")
    failures: list[str] = []
    if receipt.get("format") != WORKER_CLEANUP_RECEIPT_FORMAT:
        failures.append(f"cleanup receipt has unexpected format: {receipt_id}")
    if receipt.get("authority") != CLEANUP_EVIDENCE_AUTHORITY:
        failures.append(f"cleanup receipt has unexpected authority: {receipt_id}")
    if not _is_text(receipt.get("created_at")):
        failures.append(f"cleanup receipt created_at must be non-empty: {receipt_id}")
    if receipt.get("run_id") != run.run_id:
        failures.append(f"cleanup receipt run_id mismatch: {receipt_id}")
    worker = index.workers.get(worker_id)
    if worker is None:
        failures.append(f"cleanup receipt references unknown worker: {receipt_id}")
    elif receipt.get("backend") != worker.backend.value:
        failures.append(f"cleanup receipt backend mismatch: {receipt_id}")
    required = index.required_by_wave.get(wave_id)
    if required is None:
        failures.append(f"cleanup receipt references unknown wave: {receipt_id}")
    elif worker_id not in required:
        failures.append(f"cleanup receipt worker is not required by wave: {receipt_id}")
    for field in ("backend_worker_ref", "resource_lease_ref", "resource_lease_id"):
        if not _is_text(receipt.get(field)):
            failures.append(f"cleanup receipt {field} must be non-empty: {receipt_id}")
    if receipt.get("cleanup_capability") != CLEANUP_CAPABILITY:
        failures.append(f"cleanup receipt has unsupported cleanup_capability: {receipt_id}")
    try:
        status = CleanupStatus(str(receipt.get("cleanup_status") or ""))
    except ValueError:
        failures.append(f"cleanup receipt has unsupported status: {receipt_id}")
        status = None
    resource_fields = (
        "released_resource_ids",
        "preserved_resource_ids",
        "failed_resource_ids",
    )
    resources = {
        field: _text_list(receipt.get(field), f"cleanup receipt {receipt_id} {field}")
        for field in resource_fields
    }
    for field, values in resources.items():
        if not _unique(values):
            failures.append(f"cleanup receipt {field} must be unique: {receipt_id}")
    all_resources = tuple(item for values in resources.values() for item in values)
    if not _unique(all_resources):
        failures.append(f"cleanup receipt resource sets must be disjoint: {receipt_id}")
    proof_refs = _text_list(receipt.get("proof_refs"), f"cleanup receipt {receipt_id} proof_refs")
    if not proof_refs or not _unique(proof_refs):
        failures.append(f"cleanup receipt proof_refs must be non-empty and unique: {receipt_id}")
    blocker = receipt.get("blocker")
    if blocker is not None and not _is_text(blocker):
        failures.append(f"cleanup receipt blocker must be non-empty or null: {receipt_id}")
    target_field = {
        CleanupStatus.RELEASED: "released_resource_ids",
        CleanupStatus.PRESERVED: "preserved_resource_ids",
        CleanupStatus.FAILED: "failed_resource_ids",
        CleanupStatus.AUDIT_ONLY: "preserved_resource_ids",
    }.get(status)
    if target_field is not None:
        if not resources[target_field]:
            failures.append(f"cleanup receipt {status.value} requires {target_field}: {receipt_id}")
        if any(resources[field] for field in resource_fields if field != target_field):
            failures.append(f"cleanup receipt {status.value} has incompatible resource sets: {receipt_id}")
        if receipt.get("backend_worker_ref") not in resources[target_field]:
            failures.append(f"cleanup receipt resource set does not bind backend worker: {receipt_id}")
    if status is CleanupStatus.RELEASED and blocker is not None:
        failures.append(f"released cleanup receipt cannot carry blocker: {receipt_id}")
    if status is not None and status is not CleanupStatus.RELEASED and not _is_text(blocker):
        failures.append(f"nonreleased cleanup receipt requires blocker: {receipt_id}")
    return failures


def _fan_in_failures(run: DelegationRun, receipt: JsonObject) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    failures = _receipt_boundary_failures(receipt, fan_in=True)
    if receipt.get("run_id") != run.run_id:
        failures.append(f"fan-in receipt run_id mismatch: {receipt_id}")
    fields = ["required_worker_ids", "terminal_receipt_ids", "blocking_receipt_ids"]
    if "cleanup_receipt_ids" in receipt:
        fields.append("cleanup_receipt_ids")
    for field in fields:
        values = _text_list(receipt.get(field), f"fan-in receipt {receipt_id} {field}")
        if not _unique(values):
            failures.append(f"fan-in receipt {field} must be unique: {receipt_id}")
    if receipt.get("aggregate_status") not in {
        WaveStatus.PASSED.value,
        WaveStatus.FAILED.value,
        WaveStatus.BLOCKED.value,
    }:
        failures.append(f"fan-in receipt has unsupported aggregate_status: {receipt_id}")
    return failures


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
    provisional = _RunIndex(workers, waves, required_by_wave, wave_by_worker, {}, {}, {}, {}, {})
    for receipt in run.receipts:
        receipt_type = receipt.get("receipt_type")
        if receipt_type == "worker_terminal":
            failures.extend(_terminal_failures(run, provisional, receipt))
            terminals_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
            terminals_by_worker[str(receipt.get("worker_id") or "")].append(receipt)
            continue
        if receipt_type == "worker_cleanup":
            failures.extend(_cleanup_failures(run, provisional, receipt))
            cleanups_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
            cleanups_by_worker[str(receipt.get("worker_id") or "")].append(receipt)
            continue
        if receipt_type == "fan_in":
            failures.extend(_fan_in_failures(run, receipt))
            fan_ins_by_wave[str(receipt.get("wave_id") or "")].append(receipt)
            continue
        failures.append(f"unsupported receipt type: {receipt.get('receipt_id')}")
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
    receipts: tuple[JsonObject, ...],
    cleanup_receipts: tuple[JsonObject, ...],
) -> str | None:
    statuses = {receipt.get("terminal_status") for receipt in receipts}
    supported = {status.value for status in TerminalStatus}
    if not statuses or not statuses.issubset(supported):
        return None
    cleanup_statuses = {receipt.get("cleanup_status") for receipt in cleanup_receipts}
    if not cleanup_statuses.issubset({status.value for status in CleanupStatus}):
        return None
    if (
        TerminalStatus.FAILED.value in statuses
        or TerminalStatus.TIMED_OUT.value in statuses
        or CleanupStatus.FAILED.value in cleanup_statuses
    ):
        return WaveStatus.FAILED.value
    if statuses == {TerminalStatus.COMPLETED.value} and cleanup_statuses.issubset(
        {CleanupStatus.RELEASED.value}
    ):
        return WaveStatus.PASSED.value
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
        cleanup_count = len(index.cleanups_by_worker.get(worker_id, ()))
        if cleanup_count > 1:
            failures.append(f"worker must have at most one cleanup receipt: {worker_id}")
        if cleanup_count and receipt_count != 1:
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
    cleanup_claim = _text_list(
        fan_in.get("cleanup_receipt_ids", []),
        f"fan-in {wave_id} cleanup_receipt_ids",
    )
    blocking_claim = _text_list(fan_in.get("blocking_receipt_ids"), f"fan-in {wave_id} blocking_receipt_ids")
    terminal_ids = tuple(str(receipt.get("receipt_id") or "") for receipt in terminals)
    terminal_workers = tuple(str(receipt.get("worker_id") or "") for receipt in terminals)
    cleanup_ids = tuple(str(receipt.get("receipt_id") or "") for receipt in cleanups)
    blocking_ids = tuple([
        str(receipt.get("receipt_id") or "")
        for receipt in terminals
        if receipt.get("terminal_status") != TerminalStatus.COMPLETED.value
    ] + [
        str(receipt.get("receipt_id") or "")
        for receipt in cleanups
        if receipt.get("cleanup_status") != CleanupStatus.RELEASED.value
    ])
    if not _unique(required_claim) or set(required_claim) != set(required):
        failures.append(f"fan-in required workers do not exactly cover wave: {wave_id}")
    if not _unique(terminal_claim) or set(terminal_claim) != set(terminal_ids):
        failures.append(f"fan-in terminal receipts do not exactly cover wave: {wave_id}")
    if not _unique(cleanup_claim) or set(cleanup_claim) != set(cleanup_ids):
        failures.append(f"fan-in cleanup receipts do not exactly cover supplied evidence: {wave_id}")
    if not _unique(terminal_workers) or set(terminal_workers) != set(required):
        failures.append(f"terminal receipts do not exactly cover wave workers: {wave_id}")
    aggregate = _expected_aggregate(terminals, cleanups)
    if aggregate is None or fan_in.get("aggregate_status") != aggregate or status != aggregate:
        failures.append(f"fan-in aggregate_status does not match terminal and cleanup evidence: {wave_id}")
    if not _unique(blocking_claim) or set(blocking_claim) != set(blocking_ids):
        failures.append(f"fan-in blocking receipts do not match terminal and cleanup evidence: {wave_id}")
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
    for wave_id in index.cleanups_by_wave:
        if wave_id not in index.waves:
            failures.append(f"cleanup receipt references unknown wave: {wave_id}")
    return tuple(failures)
