from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from delegation_cleanup import (
    CLEANUP_AUTHORITY,
    CLEANUP_RECEIPT_FORMAT,
    CleanupCapability,
    CleanupStatus,
)
from delegation_run_model import JsonObject, JsonValue, Worker
from delegation_wave import (
    EVIDENCE_AUTHORITY,
    FAN_IN_AUTHORITY,
    FAN_IN_RECEIPT_FORMAT,
    WORKER_RECEIPT_FORMAT,
    TerminalStatus,
    WaveStatus,
    _text_list,
)


@dataclass(frozen=True, slots=True)
class ReceiptValidationContext:
    run_id: str
    workers: dict[str, Worker]
    required_by_wave: dict[str, tuple[str, ...]]


class ReceiptType(StrEnum):
    WORKER_TERMINAL = "worker_terminal"
    WORKER_CLEANUP = "worker_cleanup"
    FAN_IN = "fan_in"


def parse_receipt_type(receipt: JsonObject) -> ReceiptType | None:
    try:
        return ReceiptType(str(receipt.get("receipt_type") or ""))
    except ValueError:
        return None


def _is_text(value: JsonValue) -> bool:
    return isinstance(value, str) and bool(value)


def _unique(values: tuple[str, ...]) -> bool:
    return len(values) == len(set(values))


def _boundary_failures(
    receipt: JsonObject,
    expected_format: str,
    expected_authority: str,
) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    failures: list[str] = []
    if receipt.get("format") != expected_format:
        failures.append(f"receipt has unexpected format: {receipt_id}")
    if receipt.get("authority") != expected_authority:
        failures.append(f"receipt has unexpected authority: {receipt_id}")
    if not _is_text(receipt.get("created_at")):
        failures.append(f"receipt created_at must be non-empty: {receipt_id}")
    return failures


def _terminal_failures(
    context: ReceiptValidationContext,
    receipt: JsonObject,
) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    wave_id = str(receipt.get("wave_id") or "")
    worker_id = str(receipt.get("worker_id") or "")
    failures = _boundary_failures(receipt, WORKER_RECEIPT_FORMAT, EVIDENCE_AUTHORITY)
    if receipt.get("run_id") != context.run_id:
        failures.append(f"terminal receipt run_id mismatch: {receipt_id}")
    worker = context.workers.get(worker_id)
    if worker is None:
        failures.append(f"terminal receipt references unknown worker: {receipt_id}")
    elif receipt.get("backend") != worker.backend.value:
        failures.append(f"terminal receipt backend mismatch: {receipt_id}")
    required = context.required_by_wave.get(wave_id)
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


def _cleanup_failures(
    context: ReceiptValidationContext,
    receipt: JsonObject,
) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    wave_id = str(receipt.get("wave_id") or "")
    worker_id = str(receipt.get("worker_id") or "")
    failures = _boundary_failures(receipt, CLEANUP_RECEIPT_FORMAT, CLEANUP_AUTHORITY)
    if receipt.get("run_id") != context.run_id:
        failures.append(f"cleanup receipt run_id mismatch: {receipt_id}")
    worker = context.workers.get(worker_id)
    if worker is None:
        failures.append(f"cleanup receipt references unknown worker: {receipt_id}")
    elif receipt.get("backend") != worker.backend.value:
        failures.append(f"cleanup receipt backend mismatch: {receipt_id}")
    required = context.required_by_wave.get(wave_id)
    if required is None or worker_id not in required:
        failures.append(f"cleanup receipt worker is not required by wave: {receipt_id}")
    for field in ("backend_worker_ref", "resource_lease_ref", "resource_lease_id"):
        if not _is_text(receipt.get(field)):
            failures.append(f"cleanup receipt {field} must be non-empty: {receipt_id}")
    try:
        capability = CleanupCapability(str(receipt.get("cleanup_capability") or ""))
        status = CleanupStatus(str(receipt.get("cleanup_status") or ""))
    except ValueError:
        failures.append(f"cleanup receipt has unsupported capability or status: {receipt_id}")
        return failures
    resource_lists = {
        field: _text_list(receipt.get(field), f"cleanup receipt {receipt_id} {field}")
        for field in ("released_resource_ids", "preserved_resource_ids", "failed_resource_ids")
    }
    flattened = tuple(value for values in resource_lists.values() for value in values)
    if len(flattened) != len(set(flattened)):
        failures.append(f"cleanup receipt resource ids must be unique and disjoint: {receipt_id}")
    proof_refs = _text_list(receipt.get("proof_refs"), f"cleanup receipt {receipt_id} proof_refs")
    if not proof_refs or not _unique(proof_refs):
        failures.append(f"cleanup receipt proof_refs must be unique and non-empty: {receipt_id}")
    blocker = receipt.get("blocker")
    match status:
        case CleanupStatus.RELEASED:
            if capability is CleanupCapability.AUDIT_ONLY or not resource_lists["released_resource_ids"]:
                failures.append(f"released cleanup requires exact released resources: {receipt_id}")
            if resource_lists["preserved_resource_ids"] or resource_lists["failed_resource_ids"] or blocker is not None:
                failures.append(f"released cleanup cannot carry unresolved resources or blocker: {receipt_id}")
        case CleanupStatus.PRESERVED:
            if not resource_lists["preserved_resource_ids"] or not _is_text(blocker):
                failures.append(f"preserved cleanup requires resources and blocker: {receipt_id}")
        case CleanupStatus.FAILED:
            if not resource_lists["failed_resource_ids"] or not _is_text(blocker):
                failures.append(f"failed cleanup requires resources and blocker: {receipt_id}")
        case CleanupStatus.AUDIT_ONLY:
            if capability is not CleanupCapability.AUDIT_ONLY or not _is_text(blocker):
                failures.append(f"audit-only cleanup requires audit capability and blocker: {receipt_id}")
        case unreachable:
            assert_never(unreachable)
    return failures


def _fan_in_failures(receipt: JsonObject, run_id: str) -> list[str]:
    receipt_id = str(receipt.get("receipt_id") or "")
    failures = _boundary_failures(receipt, FAN_IN_RECEIPT_FORMAT, FAN_IN_AUTHORITY)
    if receipt.get("run_id") != run_id:
        failures.append(f"fan-in receipt run_id mismatch: {receipt_id}")
    for field in ("required_worker_ids", "terminal_receipt_ids", "cleanup_receipt_ids", "blocking_receipt_ids"):
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


def receipt_failures(
    context: ReceiptValidationContext,
    receipt: JsonObject,
) -> tuple[str, ...]:
    match parse_receipt_type(receipt):
        case ReceiptType.WORKER_TERMINAL:
            failures = _terminal_failures(context, receipt)
        case ReceiptType.WORKER_CLEANUP:
            failures = _cleanup_failures(context, receipt)
        case ReceiptType.FAN_IN:
            failures = _fan_in_failures(receipt, context.run_id)
        case None:
            failures = [f"unsupported receipt type: {receipt.get('receipt_id')}"]
        case unreachable:
            assert_never(unreachable)
    return tuple(failures)
