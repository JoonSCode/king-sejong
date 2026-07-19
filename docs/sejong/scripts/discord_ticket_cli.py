#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from codex_process_contract import CodexProcessRequest
from codex_ticket_runner import ProcessResult, TicketRunSpec, TicketRunner
from discord_contract_types import ControlContractError, CreateTicketCommand, JsonObject, JsonValue
from discord_control_contract import parse_inbound_event
from discord_idempotency import IdempotencyStatus, IdempotencyStore
from discord_target_registry import TargetRegistry


@dataclass(frozen=True, slots=True)
class DryRunRequest:
    event_path: Path
    policy_path: Path
    targets_path: Path
    workspace: Path
    sejong_home: Path


class _RejectLiveProcess:
    def run(self, request: CodexProcessRequest, cancellation_path: Path) -> ProcessResult:
        raise AssertionError(f"dry-run attempted live process for {request.ticket_id}")


def _load(path: Path) -> JsonValue:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlContractError("malformed_input", f"cannot parse {path}") from exc


def run_dry_ticket(request: DryRunRequest) -> JsonObject:
    event = parse_inbound_event(_load(request.event_path), _load(request.policy_path))
    if not isinstance(event.command, CreateTicketCommand):
        raise ControlContractError("wrong_command", "dry-run entry point requires create_ticket")
    ticket = event.command.ticket
    if not ticket.dry_run:
        raise ControlContractError("dry_run_required", "entry point cannot execute a live ticket")
    target = TargetRegistry.load(request.targets_path).resolve(ticket.host_id, ticket.repo_id)
    if not request.workspace.is_absolute() or not request.sejong_home.is_absolute():
        raise ControlContractError("malformed_input", "workspace and SEJONG_HOME must be absolute")
    decision = IdempotencyStore(
        request.sejong_home / "state" / "discord" / "idempotency.json"
    ).accept(event)
    if decision.status is not IdempotencyStatus.ACCEPTED:
        raise ControlContractError("duplicate_event", "dry-run event was already handled")
    result = TicketRunner(_RejectLiveProcess()).run(TicketRunSpec(
        ticket=ticket,
        target=target,
        workspace=request.workspace,
        sejong_home=request.sejong_home,
        delegation=None,
    ))
    return {
        "format": "sejong.discord-ticket-dry-run/v0.1-draft",
        "ticket_id": ticket.ticket_id,
        "status": result.status.value,
        "process_invoked": False,
        "receipt_path": str(result.receipt_path),
        "idempotency_status": decision.status.value,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local contract-only Discord ticket dry run.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--event", type=Path, required=True)
    dry_run.add_argument("--policy", type=Path, required=True)
    dry_run.add_argument("--targets", type=Path, required=True)
    dry_run.add_argument("--workspace", type=Path, required=True)
    dry_run.add_argument("--sejong-home", type=Path, required=True)
    dry_run.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        output = run_dry_ticket(DryRunRequest(
            args.event.resolve(),
            args.policy.resolve(),
            args.targets.resolve(),
            args.workspace.resolve(),
            args.sejong_home.resolve(),
        ))
    except ControlContractError as exc:
        print(json.dumps({"status": "error", "code": exc.code, "detail": exc.detail}), file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True) if args.json else output["receipt_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
