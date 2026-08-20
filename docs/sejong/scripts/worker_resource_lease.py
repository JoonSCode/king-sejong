#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
#   uv run docs/sejong/scripts/worker_resource_lease.py --help
# ──────────────────────────

from __future__ import annotations

import argparse
import sys
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from delegation_run_model import DelegationContractError
from worker_resource_model import (
    CleanupCapability,
    CleanupPolicy,
    LeaseCreateRequest,
    LeaseOwner,
    LeaseStatus,
    OwnershipSource,
    ResourceKind,
    ResourceRecord,
    create_lease,
    load_lease,
    locked_lease,
    save_lease,
    transition_lease,
)


class LeaseCommand(StrEnum):
    CREATE = "create"
    TRANSITION = "transition"
    CHECK = "check"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage exact worker resource ownership leases.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create one active worker resource lease")
    create.add_argument("path", type=Path)
    create.add_argument("--lease-id", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--wave-id", required=True)
    create.add_argument("--worker-id", required=True)
    create.add_argument("--backend", required=True)
    create.add_argument("--backend-worker-ref", required=True)
    create.add_argument("--cleanup-capability", required=True, choices=[item.value for item in CleanupCapability])
    create.add_argument("--resource-id", required=True)
    create.add_argument("--resource-kind", required=True, choices=[item.value for item in ResourceKind])
    create.add_argument("--identity-ref", required=True)
    create.add_argument("--ownership-source", required=True, choices=[item.value for item in OwnershipSource])
    create.add_argument("--cleanup-policy", required=True, choices=[item.value for item in CleanupPolicy])
    transition = commands.add_parser("transition", help="Advance an existing worker resource lease")
    transition.add_argument("path", type=Path)
    transition.add_argument("--status", required=True, choices=[item.value for item in LeaseStatus])
    transition.add_argument("--proof-ref", action="append")
    transition.add_argument("--blocker")
    check = commands.add_parser("check", help="Validate a persisted worker resource lease")
    check.add_argument("path", type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> None:
    with locked_lease(args.path):
        match LeaseCommand(args.command):
            case LeaseCommand.CREATE:
                if args.path.exists():
                    raise DelegationContractError(f"worker resource lease already exists: {args.path}")
                resource = ResourceRecord(
                    resource_id=args.resource_id,
                    kind=ResourceKind(args.resource_kind),
                    identity_ref=args.identity_ref,
                    ownership_source=OwnershipSource(args.ownership_source),
                    cleanup_policy=CleanupPolicy(args.cleanup_policy),
                    status=LeaseStatus.ACTIVE,
                )
                lease = create_lease(
                    LeaseCreateRequest(
                        lease_id=args.lease_id,
                        owner=LeaseOwner(
                            run_id=args.run_id,
                            wave_id=args.wave_id,
                            worker_id=args.worker_id,
                            backend=args.backend,
                            backend_worker_ref=args.backend_worker_ref,
                        ),
                        cleanup_capability=CleanupCapability(args.cleanup_capability),
                        resource=resource,
                    )
                )
                save_lease(args.path, lease)
            case LeaseCommand.TRANSITION:
                updated = transition_lease(
                    load_lease(args.path),
                    LeaseStatus(args.status),
                    tuple(args.proof_ref or ()),
                    args.blocker,
                )
                save_lease(args.path, updated)
            case LeaseCommand.CHECK:
                load_lease(args.path)
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
