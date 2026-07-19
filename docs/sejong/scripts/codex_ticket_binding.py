from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, assert_never

from delegation_run_model import Backend, WorkerId, WorkerStatus, load_run
from discord_contract_types import ControlContractError, JsonObject, JsonValue, SandboxMode, TicketIntent
from team_executor import scope_matches


@dataclass(frozen=True, slots=True)
class DelegationBinding:
    team_run_dir: Path
    delegation_run_path: Path
    worker_id: str
    wave_id: str
    worker_contract_ref: str
    lease_refs: tuple[str, ...]


class BindingSpec(Protocol):
    ticket: TicketIntent
    workspace: Path
    sejong_home: Path
    delegation: DelegationBinding | None


def _object(value: JsonValue, field: str) -> JsonObject:
    match value:
        case dict():
            return value
        case str() | int() | float() | bool() | None | list():
            raise ControlContractError("invalid_delegation", f"{field} must be an object")
        case unreachable:
            assert_never(unreachable)


def _objects(value: JsonValue, field: str) -> tuple[JsonObject, ...]:
    match value:
        case list():
            return tuple(_object(item, field) for item in value)
        case str() | int() | float() | bool() | None | dict():
            raise ControlContractError("invalid_delegation", f"{field} must be an array")
        case unreachable:
            assert_never(unreachable)


def _load(path: Path, expected_format: str) -> JsonObject:
    try:
        raw: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlContractError("invalid_delegation", f"cannot read {path.name}: {exc}") from exc
    payload = _object(raw, path.name)
    if payload.get("format") != expected_format:
        raise ControlContractError("invalid_delegation", f"unexpected {path.name} format")
    return payload


def _lease_scopes(lease: JsonObject) -> tuple[str, ...]:
    value = lease.get("scopes")
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ControlContractError("invalid_delegation", "lease scopes must be an array of non-empty paths")
    return tuple(value)


def validate_delegation_binding(spec: BindingSpec) -> None:
    binding = spec.delegation
    if binding is None:
        if spec.ticket.sandbox is SandboxMode.WORKSPACE_WRITE or spec.ticket.write_paths:
            raise ControlContractError(
                "delegation_required",
                "executable write ticket requires an existing Core/TeamExecutor binding",
            )
        return
    team_root = spec.sejong_home / "state" / "team"
    if not binding.team_run_dir.is_relative_to(team_root):
        raise ControlContractError("invalid_delegation", "TeamExecutor state must be under SEJONG_HOME")
    if not binding.delegation_run_path.is_relative_to(spec.sejong_home):
        raise ControlContractError("invalid_delegation", "delegation run must be under SEJONG_HOME")
    team = _load(binding.team_run_dir / "team.json", "sejong.team/v0.1-draft")
    if Path(str(team.get("delegation_run_ref"))).resolve() != binding.delegation_run_path.resolve():
        raise ControlContractError("invalid_delegation", "TeamExecutor delegation reference differs")
    workers = _objects(team.get("workers"), "workers")
    worker = next((item for item in workers if item.get("worker_id") == binding.worker_id), None)
    if worker is None:
        raise ControlContractError("invalid_delegation", "TeamExecutor worker is not registered")
    isolation = _object(worker.get("isolation"), "worker.isolation")
    if isolation.get("backend") != "worktree" or Path(str(isolation.get("workspace_path"))) != spec.workspace:
        raise ControlContractError("invalid_delegation", "write ticket is not bound to its TeamExecutor worktree")
    leases = _load(binding.team_run_dir / "leases.json", "sejong.team-leases/v0.1-draft")
    active = tuple(
        item
        for item in _objects(leases.get("leases"), "leases")
        if item.get("status") == "active" and item.get("worker_id") == binding.worker_id
    )
    active_ids = {item.get("lease_id") for item in active}
    if not binding.lease_refs or not set(binding.lease_refs).issubset(active_ids):
        raise ControlContractError("lease_required", "write ticket requires every declared active lease")
    scopes = tuple(
        scope
        for lease in active
        for scope in _lease_scopes(lease)
    )
    if any(not any(scope_matches(scope, path) for scope in scopes) for path in spec.ticket.write_paths):
        raise ControlContractError("lease_required", "active leases do not cover the ticket write scope")
    delegation = load_run(binding.delegation_run_path)
    core_worker = next(
        (item for item in delegation.workers if item.worker_id == WorkerId(binding.worker_id)),
        None,
    )
    if core_worker is None or core_worker.backend is not Backend.TEAM_EXECUTOR:
        raise ControlContractError("invalid_delegation", "worker is not bound to Core TeamExecutor authority")
    if core_worker.status is not WorkerStatus.LAUNCHED:
        raise ControlContractError("invalid_delegation", "Core worker concurrency is not reserved")
    wave = next((item for item in delegation.waves if item.get("wave_id") == binding.wave_id), None)
    if wave is None or wave.get("status") != "active":
        raise ControlContractError("invalid_delegation", "Core delegation wave is not active")
