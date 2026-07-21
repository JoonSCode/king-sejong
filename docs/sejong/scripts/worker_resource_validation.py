from __future__ import annotations

from delegation_run_model import DelegationContractError
from worker_resource_model import (
    CleanupCapability,
    LeaseStatus,
    OwnershipSource,
    ResourceKind,
    WorkerResourceLease,
)


def validate_lease(lease: WorkerResourceLease) -> None:
    resource_ids = tuple(resource.resource_id for resource in lease.resources)
    if not resource_ids or len(resource_ids) != len(set(resource_ids)):
        raise DelegationContractError("worker resource ids must be unique and non-empty")
    if any(resource.status is not lease.status for resource in lease.resources):
        raise DelegationContractError("resource status must match lease status")
    expected_source = {
        CleanupCapability.CORE_OWNED_EXACT: OwnershipSource.SEJONG_CREATED,
        CleanupCapability.HOST_OWNED_EXACT: OwnershipSource.HOST_REPORTED,
        CleanupCapability.AUDIT_ONLY: OwnershipSource.OBSERVED,
    }[lease.cleanup_capability]
    if any(resource.ownership_source is not expected_source for resource in lease.resources):
        raise DelegationContractError("cleanup capability must match resource ownership source")
    if any(
        resource.kind is ResourceKind.HOST_RUNTIME_GROUP
        and resource.identity_ref != lease.owner.backend_worker_ref
        for resource in lease.resources
    ):
        raise DelegationContractError("host runtime identity must match backend worker ref")
    if len(lease.proof_refs) != len(set(lease.proof_refs)) or any(not ref for ref in lease.proof_refs):
        raise DelegationContractError("worker resource proof refs must be unique and non-empty")
    is_terminal = lease.status in {
        LeaseStatus.RELEASED,
        LeaseStatus.PRESERVED,
        LeaseStatus.FAILED,
        LeaseStatus.ORPHANED,
    }
    if is_terminal and not lease.proof_refs:
        raise DelegationContractError("terminal worker resource lease requires proof refs")
    if lease.status is LeaseStatus.RELEASED:
        if lease.cleanup_capability is CleanupCapability.AUDIT_ONLY or lease.blocker is not None:
            raise DelegationContractError("released lease requires exact ownership without blocker")
    elif is_terminal and not lease.blocker:
        raise DelegationContractError("unresolved worker resource lease requires blocker")
