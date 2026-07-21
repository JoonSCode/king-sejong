from __future__ import annotations

import fcntl
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final, NewType, assert_never

from delegation_run_model import (
    DelegationContractError,
    DelegationRun,
    JsonObject,
    WorkerId,
    now_utc,
    load_run,
    save_run,
)


CLEANUP_RECEIPT_FORMAT: Final = "sejong.worker-cleanup-receipt/v0.1-draft"
CLEANUP_AUTHORITY: Final = "cleanup_evidence_only"
CleanupReceiptId = NewType("CleanupReceiptId", str)


class CleanupCapability(StrEnum):
    CORE_OWNED_EXACT = "core_owned_exact"
    HOST_OWNED_EXACT = "host_owned_exact"
    AUDIT_ONLY = "audit_only"


class CleanupStatus(StrEnum):
    RELEASED = "released"
    PRESERVED = "preserved"
    FAILED = "failed"
    AUDIT_ONLY = "audit_only"


@dataclass(frozen=True, slots=True)
class CleanupReceiptRequest:
    receipt_id: CleanupReceiptId
    wave_id: str
    worker_id: WorkerId
    backend_worker_ref: str
    resource_lease_ref: str
    resource_lease_id: str
    cleanup_capability: CleanupCapability
    cleanup_status: CleanupStatus
    released_resource_ids: tuple[str, ...]
    preserved_resource_ids: tuple[str, ...]
    failed_resource_ids: tuple[str, ...]
    proof_refs: tuple[str, ...]
    blocker: str | None


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _required_workers(run: DelegationRun, wave_id: str) -> tuple[str, ...]:
    wave = next((item for item in run.waves if item.get("wave_id") == wave_id), None)
    if wave is None:
        raise DelegationContractError(f"unknown wave: {wave_id}")
    if wave.get("status") != "active":
        raise DelegationContractError(f"wave is not active: {wave_id}")
    required = wave.get("required_worker_ids")
    if not isinstance(required, list) or not all(isinstance(item, str) and item for item in required):
        raise DelegationContractError(f"wave workers are invalid: {wave_id}")
    return tuple(item for item in required if isinstance(item, str))


def _validate_resource_sets(request: CleanupReceiptRequest) -> None:
    groups = (
        request.released_resource_ids,
        request.preserved_resource_ids,
        request.failed_resource_ids,
    )
    for values in groups:
        if len(values) != len(set(values)) or any(not value for value in values):
            raise DelegationContractError("cleanup resource ids must be non-empty")
    flattened = tuple(value for values in groups for value in values)
    if len(flattened) != len(set(flattened)):
        raise DelegationContractError("cleanup resource sets must be disjoint")
    if not request.proof_refs or len(request.proof_refs) != len(set(request.proof_refs)):
        raise DelegationContractError("cleanup proof refs must be unique and non-empty")
    if any(not reference for reference in request.proof_refs):
        raise DelegationContractError("cleanup proof refs must be unique and non-empty")


def _validate_status(request: CleanupReceiptRequest) -> None:
    match request.cleanup_status:
        case CleanupStatus.RELEASED:
            if request.cleanup_capability is CleanupCapability.AUDIT_ONLY:
                raise DelegationContractError("audit-only cleanup cannot claim released")
            if not request.released_resource_ids or request.preserved_resource_ids or request.failed_resource_ids:
                raise DelegationContractError("released cleanup must release every resource")
            if request.blocker is not None:
                raise DelegationContractError("released cleanup cannot carry blocker")
        case CleanupStatus.PRESERVED:
            if not request.preserved_resource_ids or not request.blocker:
                raise DelegationContractError("preserved cleanup requires resources and blocker")
        case CleanupStatus.FAILED:
            if not request.failed_resource_ids or not request.blocker:
                raise DelegationContractError("failed cleanup requires resources and blocker")
        case CleanupStatus.AUDIT_ONLY:
            if request.cleanup_capability is not CleanupCapability.AUDIT_ONLY or not request.blocker:
                raise DelegationContractError("audit-only cleanup requires audit capability and blocker")
        case unreachable:
            assert_never(unreachable)


def cleanup_required_worker_ids(receipts: Iterable[JsonObject]) -> frozenset[str]:
    return frozenset(
        str(receipt.get("worker_id"))
        for receipt in receipts
        if str(receipt.get("backend_worker_ref") or "").startswith("codex-thread://")
    )


def record_cleanup(run: DelegationRun, request: CleanupReceiptRequest) -> DelegationRun:
    from delegation_wave_validation import persisted_wave_failures

    if failures := persisted_wave_failures(run):
        raise DelegationContractError(f"invalid persisted wave state: {'; '.join(failures)}")
    required = _required_workers(run, request.wave_id)
    if request.worker_id not in required:
        raise DelegationContractError(f"worker is not required by wave: {request.worker_id}")
    terminal = [
        receipt
        for receipt in run.receipts
        if receipt.get("receipt_type") == "worker_terminal"
        and receipt.get("wave_id") == request.wave_id
        and receipt.get("worker_id") == request.worker_id
    ]
    if len(terminal) != 1:
        raise DelegationContractError(f"cleanup requires one terminal receipt: {request.worker_id}")
    if terminal[0].get("backend_worker_ref") != request.backend_worker_ref:
        raise DelegationContractError(f"cleanup backend worker ref mismatch: {request.worker_id}")
    if any(receipt.get("receipt_id") == request.receipt_id for receipt in run.receipts):
        raise DelegationContractError(f"receipt already exists: {request.receipt_id}")
    if any(
        receipt.get("receipt_type") == "worker_cleanup" and receipt.get("worker_id") == request.worker_id
        for receipt in run.receipts
    ):
        raise DelegationContractError(f"cleanup receipt already exists: {request.worker_id}")
    worker = next(item for item in run.workers if item.worker_id == request.worker_id)
    _validate_resource_sets(request)
    _validate_status(request)
    receipt: JsonObject = {
        "format": CLEANUP_RECEIPT_FORMAT,
        "receipt_type": "worker_cleanup",
        "receipt_id": request.receipt_id,
        "run_id": run.run_id,
        "wave_id": request.wave_id,
        "worker_id": request.worker_id,
        "backend": worker.backend.value,
        "backend_worker_ref": request.backend_worker_ref,
        "resource_lease_ref": request.resource_lease_ref,
        "resource_lease_id": request.resource_lease_id,
        "cleanup_capability": request.cleanup_capability.value,
        "cleanup_status": request.cleanup_status.value,
        "released_resource_ids": list(request.released_resource_ids),
        "preserved_resource_ids": list(request.preserved_resource_ids),
        "failed_resource_ids": list(request.failed_resource_ids),
        "proof_refs": list(request.proof_refs),
        "blocker": request.blocker,
        "authority": CLEANUP_AUTHORITY,
        "created_at": now_utc(),
    }
    return replace(run, receipts=(*run.receipts, receipt))


def record_cleanup_receipt(path: Path, request: CleanupReceiptRequest) -> None:
    with _locked(path):
        save_run(path, record_cleanup(load_run(path), request))
