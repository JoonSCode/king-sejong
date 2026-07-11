from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Final, NewType, TypeAlias


FORMAT: Final = "sejong.delegation-run/v0.1-draft"
BUDGET_REF: Final = "#/budget"
WorkerId = NewType("WorkerId", str)
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class Backend(StrEnum):
    NATIVE = "native"
    TEAM_EXECUTOR = "team_executor"


class WorkerStatus(StrEnum):
    REGISTERED = "registered"
    LAUNCHED = "launched"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"


TERMINAL_STATUSES: Final = frozenset(
    {WorkerStatus.COMPLETED, WorkerStatus.FAILED, WorkerStatus.TIMED_OUT, WorkerStatus.BLOCKED}
)


@dataclass(slots=True)
class DelegationContractError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class Budget:
    max_total_workers: int
    max_concurrency: int
    max_spawn_depth: int
    max_rounds: int

    def failures(self) -> tuple[str, ...]:
        failures = []
        if self.max_total_workers < 1:
            failures.append("max_total_workers must be positive")
        if self.max_concurrency < 1:
            failures.append("max_concurrency must be positive")
        if self.max_spawn_depth < 0:
            failures.append("max_spawn_depth must be non-negative")
        if self.max_rounds < 1:
            failures.append("max_rounds must be positive")
        if self.max_concurrency > self.max_total_workers:
            failures.append("max_concurrency cannot exceed max_total_workers")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
class Worker:
    worker_id: WorkerId
    backend: Backend
    spawn_depth: int
    status: WorkerStatus = WorkerStatus.REGISTERED
    budget_ref: str = BUDGET_REF


@dataclass(frozen=True, slots=True)
class DelegationRun:
    run_id: str
    created_at: str
    budget: Budget
    workers: tuple[Worker, ...] = ()
    rounds_started: tuple[str, ...] = ()
    waves: tuple[JsonObject, ...] = ()
    receipts: tuple[JsonObject, ...] = ()


@dataclass(frozen=True, slots=True)
class InitRequest:
    path: Path
    run_id: str
    budget: Budget


@dataclass(frozen=True, slots=True)
class WorkerRegistration:
    worker_id: WorkerId
    backend: Backend
    spawn_depth: int


def reserve_registered_workers(run: DelegationRun, worker_ids: tuple[WorkerId, ...]) -> DelegationRun:
    if len(set(worker_ids)) != len(worker_ids):
        raise DelegationContractError("launch worker ids must be unique")
    known = {worker.worker_id: worker for worker in run.workers}
    missing = sorted(str(worker_id) for worker_id in worker_ids if worker_id not in known)
    if missing:
        raise DelegationContractError(f"unknown workers: {missing}")
    invalid = sorted(
        str(worker_id)
        for worker_id in worker_ids
        if known[worker_id].status is not WorkerStatus.REGISTERED
    )
    if invalid:
        raise DelegationContractError(f"workers are not registered: {invalid}")
    active = sum(worker.status is WorkerStatus.LAUNCHED for worker in run.workers)
    if active + len(worker_ids) > run.budget.max_concurrency:
        raise DelegationContractError("max_concurrency exceeded")
    requested = set(worker_ids)
    workers = tuple(
        replace(worker, status=WorkerStatus.LAUNCHED) if worker.worker_id in requested else worker
        for worker in run.workers
    )
    return replace(run, workers=workers)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_mapping(value: JsonValue, label: str) -> JsonObject:
    match value:
        case dict():
            return value
        case _:
            raise DelegationContractError(f"{label} must be an object")


def _require_list(value: JsonValue, label: str) -> list[JsonValue]:
    match value:
        case list():
            return value
        case _:
            raise DelegationContractError(f"{label} must be an array")


def _require_str(value: JsonValue, label: str) -> str:
    match value:
        case str() if value:
            return value
        case _:
            raise DelegationContractError(f"{label} must be a non-empty string")


def _require_int(value: JsonValue, label: str) -> int:
    match value:
        case bool():
            raise DelegationContractError(f"{label} must be an integer")
        case int():
            return value
        case _:
            raise DelegationContractError(f"{label} must be an integer")


def _parse_budget(value: JsonValue) -> Budget:
    payload = _require_mapping(value, "budget")
    budget = Budget(
        max_total_workers=_require_int(payload.get("max_total_workers"), "budget.max_total_workers"),
        max_concurrency=_require_int(payload.get("max_concurrency"), "budget.max_concurrency"),
        max_spawn_depth=_require_int(payload.get("max_spawn_depth"), "budget.max_spawn_depth"),
        max_rounds=_require_int(payload.get("max_rounds"), "budget.max_rounds"),
    )
    if failures := budget.failures():
        raise DelegationContractError("; ".join(failures))
    return budget


def _parse_worker(value: JsonValue) -> Worker:
    payload = _require_mapping(value, "worker")
    try:
        backend = Backend(_require_str(payload.get("backend"), "worker.backend"))
        status = WorkerStatus(_require_str(payload.get("status"), "worker.status"))
    except ValueError as error:
        raise DelegationContractError(f"worker has unsupported enum value: {error}") from error
    return Worker(
        worker_id=WorkerId(_require_str(payload.get("worker_id"), "worker.worker_id")),
        backend=backend,
        spawn_depth=_require_int(payload.get("spawn_depth"), "worker.spawn_depth"),
        status=status,
        budget_ref=_require_str(payload.get("budget_ref"), "worker.budget_ref"),
    )


def _parse_object_list(value: JsonValue, label: str) -> tuple[JsonObject, ...]:
    return tuple(_require_mapping(item, f"{label} item") for item in _require_list(value, label))


def load_run(path: Path) -> DelegationRun:
    try:
        raw: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DelegationContractError(f"cannot read delegation run {path}: {error}") from error
    payload = _require_mapping(raw, "delegation run")
    if payload.get("format") != FORMAT:
        raise DelegationContractError("delegation run has unexpected format")
    return DelegationRun(
        run_id=_require_str(payload.get("run_id"), "run_id"),
        created_at=_require_str(payload.get("created_at"), "created_at"),
        budget=_parse_budget(payload.get("budget")),
        workers=tuple(_parse_worker(item) for item in _require_list(payload.get("workers"), "workers")),
        rounds_started=tuple(
            _require_str(item, "rounds_started item") for item in _require_list(payload.get("rounds_started"), "rounds_started")
        ),
        waves=_parse_object_list(payload.get("waves"), "waves"),
        receipts=_parse_object_list(payload.get("receipts"), "receipts"),
    )


def _to_json(run: DelegationRun) -> JsonObject:
    return {
        "format": FORMAT,
        "run_id": run.run_id,
        "created_at": run.created_at,
        "budget": {
            "max_total_workers": run.budget.max_total_workers,
            "max_concurrency": run.budget.max_concurrency,
            "max_spawn_depth": run.budget.max_spawn_depth,
            "max_rounds": run.budget.max_rounds,
        },
        "workers": [
            {
                "worker_id": worker.worker_id,
                "backend": worker.backend.value,
                "spawn_depth": worker.spawn_depth,
                "status": worker.status.value,
                "budget_ref": worker.budget_ref,
            }
            for worker in run.workers
        ],
        "rounds_started": list(run.rounds_started),
        "waves": list(run.waves),
        "receipts": list(run.receipts),
    }


def save_run(path: Path, run: DelegationRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(_to_json(run), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
