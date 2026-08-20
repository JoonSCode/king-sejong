from __future__ import annotations

import json
import os
import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final

from delegation_run_model import DelegationContractError, JsonValue, now_utc


FORMAT: Final = "sejong.worker-resource-lease/v0.1-draft"


@contextmanager
def locked_lease(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class CleanupCapability(StrEnum):
    CORE_OWNED_EXACT = "core_owned_exact"
    HOST_OWNED_EXACT = "host_owned_exact"
    AUDIT_ONLY = "audit_only"


class LeaseStatus(StrEnum):
    ACTIVE = "active"
    RELEASING = "releasing"
    RELEASED = "released"
    PRESERVED = "preserved"
    FAILED = "failed"
    ORPHANED = "orphaned"


class ResourceKind(StrEnum):
    HOST_RUNTIME_GROUP = "host_runtime_group"
    PROCESS_GROUP = "process_group"
    WORKTREE = "worktree"
    TEMP_PATH = "temp_path"
    SIMULATOR_APP = "simulator_app"


class OwnershipSource(StrEnum):
    SEJONG_CREATED = "sejong_created"
    HOST_REPORTED = "host_reported"
    OBSERVED = "observed"


class CleanupPolicy(StrEnum):
    AUTOMATIC = "automatic"
    PRESERVE_IF_DIRTY = "preserve_if_dirty"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class LeaseOwner:
    run_id: str
    wave_id: str
    worker_id: str
    backend: str
    backend_worker_ref: str


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    resource_id: str
    kind: ResourceKind
    identity_ref: str
    ownership_source: OwnershipSource
    cleanup_policy: CleanupPolicy
    status: LeaseStatus


@dataclass(frozen=True, slots=True)
class WorkerResourceLease:
    lease_id: str
    owner: LeaseOwner
    cleanup_capability: CleanupCapability
    status: LeaseStatus
    resources: tuple[ResourceRecord, ...]
    proof_refs: tuple[str, ...]
    blocker: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LeaseCreateRequest:
    lease_id: str
    owner: LeaseOwner
    cleanup_capability: CleanupCapability
    resource: ResourceRecord


def _text(value: JsonValue, label: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise DelegationContractError(f"{label} must be a non-empty string")


def _nullable_text(value: JsonValue, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise DelegationContractError(f"{label} must be a non-empty string or null")


def _mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if isinstance(value, dict):
        return value
    raise DelegationContractError(f"{label} must be an object")


def _string_list(value: JsonValue, label: str) -> tuple[str, ...]:
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return tuple(item for item in value if isinstance(item, str))
    raise DelegationContractError(f"{label} must contain non-empty strings")


def create_lease(request: LeaseCreateRequest) -> WorkerResourceLease:
    from worker_resource_validation import validate_lease

    texts = (
        request.lease_id,
        request.owner.run_id,
        request.owner.wave_id,
        request.owner.worker_id,
        request.owner.backend,
        request.owner.backend_worker_ref,
        request.resource.resource_id,
        request.resource.identity_ref,
    )
    if any(not value for value in texts):
        raise DelegationContractError("worker resource lease identifiers must be non-empty")
    is_audit = request.cleanup_capability is CleanupCapability.AUDIT_ONLY
    is_observed = request.resource.ownership_source is OwnershipSource.OBSERVED
    if is_audit != is_observed:
        raise DelegationContractError("cleanup capability must match exact or observed ownership")
    timestamp = now_utc()
    lease = WorkerResourceLease(
        lease_id=request.lease_id,
        owner=request.owner,
        cleanup_capability=request.cleanup_capability,
        status=LeaseStatus.ACTIVE,
        resources=(replace(request.resource, status=LeaseStatus.ACTIVE),),
        proof_refs=(),
        blocker=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    validate_lease(lease)
    return lease


def transition_lease(
    lease: WorkerResourceLease,
    status: LeaseStatus,
    proof_refs: tuple[str, ...],
    blocker: str | None,
) -> WorkerResourceLease:
    from worker_resource_validation import validate_lease

    allowed = {
        LeaseStatus.ACTIVE: {LeaseStatus.RELEASING, LeaseStatus.ORPHANED},
        LeaseStatus.RELEASING: {
            LeaseStatus.RELEASED,
            LeaseStatus.PRESERVED,
            LeaseStatus.FAILED,
            LeaseStatus.ORPHANED,
        },
    }
    if status not in allowed.get(lease.status, set()):
        raise DelegationContractError(f"invalid lease transition: {lease.status.value} -> {status.value}")
    if status in {LeaseStatus.RELEASED, LeaseStatus.PRESERVED, LeaseStatus.FAILED, LeaseStatus.ORPHANED}:
        if not proof_refs or len(proof_refs) != len(set(proof_refs)):
            raise DelegationContractError("terminal lease transition requires unique proof refs")
    if status is LeaseStatus.RELEASED:
        if lease.cleanup_capability is CleanupCapability.AUDIT_ONLY:
            raise DelegationContractError("audit-only lease cannot claim released")
        if blocker is not None:
            raise DelegationContractError("released lease cannot carry blocker")
    elif status in {LeaseStatus.PRESERVED, LeaseStatus.FAILED, LeaseStatus.ORPHANED} and not blocker:
        raise DelegationContractError("unresolved lease transition requires blocker")
    updated = replace(
        lease,
        status=status,
        resources=tuple(replace(resource, status=status) for resource in lease.resources),
        proof_refs=proof_refs,
        blocker=blocker,
        updated_at=now_utc(),
    )
    validate_lease(updated)
    return updated


def load_lease(path: Path) -> WorkerResourceLease:
    from worker_resource_validation import validate_lease

    try:
        raw: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DelegationContractError(f"cannot read worker resource lease {path}: {error}") from error
    payload = _mapping(raw, "worker resource lease")
    if payload.get("format") != FORMAT:
        raise DelegationContractError("worker resource lease has unexpected format")
    owner_payload = _mapping(payload.get("owner"), "owner")
    resources_value = payload.get("resources")
    if not isinstance(resources_value, list) or not resources_value:
        raise DelegationContractError("resources must be a non-empty array")
    resources = tuple(
        ResourceRecord(
            resource_id=_text(resource.get("resource_id"), "resource_id"),
            kind=ResourceKind(_text(resource.get("kind"), "resource.kind")),
            identity_ref=_text(resource.get("identity_ref"), "resource.identity_ref"),
            ownership_source=OwnershipSource(_text(resource.get("ownership_source"), "resource.ownership_source")),
            cleanup_policy=CleanupPolicy(_text(resource.get("cleanup_policy"), "resource.cleanup_policy")),
            status=LeaseStatus(_text(resource.get("status"), "resource.status")),
        )
        for value in resources_value
        for resource in (_mapping(value, "resource"),)
    )
    lease = WorkerResourceLease(
        lease_id=_text(payload.get("lease_id"), "lease_id"),
        owner=LeaseOwner(
            run_id=_text(owner_payload.get("run_id"), "owner.run_id"),
            wave_id=_text(owner_payload.get("wave_id"), "owner.wave_id"),
            worker_id=_text(owner_payload.get("worker_id"), "owner.worker_id"),
            backend=_text(owner_payload.get("backend"), "owner.backend"),
            backend_worker_ref=_text(owner_payload.get("backend_worker_ref"), "owner.backend_worker_ref"),
        ),
        cleanup_capability=CleanupCapability(_text(payload.get("cleanup_capability"), "cleanup_capability")),
        status=LeaseStatus(_text(payload.get("status"), "status")),
        resources=resources,
        proof_refs=_string_list(payload.get("proof_refs"), "proof_refs"),
        blocker=_nullable_text(payload.get("blocker"), "blocker"),
        created_at=_text(payload.get("created_at"), "created_at"),
        updated_at=_text(payload.get("updated_at"), "updated_at"),
    )
    validate_lease(lease)
    return lease


def save_lease(path: Path, lease: WorkerResourceLease) -> None:
    payload = {
        "format": FORMAT,
        "lease_id": lease.lease_id,
        "owner": {
            "run_id": lease.owner.run_id,
            "wave_id": lease.owner.wave_id,
            "worker_id": lease.owner.worker_id,
            "backend": lease.owner.backend,
            "backend_worker_ref": lease.owner.backend_worker_ref,
        },
        "cleanup_capability": lease.cleanup_capability.value,
        "status": lease.status.value,
        "resources": [
            {
                "resource_id": resource.resource_id,
                "kind": resource.kind.value,
                "identity_ref": resource.identity_ref,
                "ownership_source": resource.ownership_source.value,
                "cleanup_policy": resource.cleanup_policy.value,
                "status": resource.status.value,
            }
            for resource in lease.resources
        ],
        "proof_refs": list(lease.proof_refs),
        "blocker": lease.blocker,
        "created_at": lease.created_at,
        "updated_at": lease.updated_at,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
