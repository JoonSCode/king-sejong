#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run docs/sejong/scripts/delegation_run.py --help
# 3. Or make executable and run:
#      chmod +x docs/sejong/scripts/delegation_run.py && ./docs/sejong/scripts/delegation_run.py --help
# ─────────────────

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from delegation_run_model import (
    BUDGET_REF,
    TERMINAL_STATUSES,
    Backend,
    Budget,
    DelegationContractError,
    DelegationRun,
    InitRequest,
    JsonObject,
    Worker,
    WorkerId,
    WorkerRegistration,
    WorkerStatus,
    load_run,
    now_utc,
    reserve_registered_workers,
    save_run,
)
from delegation_wave import (
    ReceiptId,
    TerminalReceiptRequest,
    TerminalStatus,
    WaveId,
    add_wave,
    fan_in,
    open_wave,
    record_terminal,
    wave_failures,
)


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


def initialize_run(request: InitRequest) -> None:
    if failures := request.budget.failures():
        raise DelegationContractError("; ".join(failures))
    if request.path.exists():
        raise DelegationContractError(f"delegation run already exists: {request.path}")
    save_run(request.path, DelegationRun(run_id=request.run_id, created_at=now_utc(), budget=request.budget))


def _with_registered_workers(
    run: DelegationRun,
    registrations: Sequence[WorkerRegistration],
) -> DelegationRun:
    requested_ids = tuple(registration.worker_id for registration in registrations)
    if len(set(requested_ids)) != len(requested_ids):
        raise DelegationContractError("worker ids must be unique")
    if any(registration.spawn_depth < 0 for registration in registrations):
        raise DelegationContractError("spawn_depth must be non-negative")
    existing = {worker.worker_id for worker in run.workers}
    duplicates = sorted(str(worker_id) for worker_id in requested_ids if worker_id in existing)
    if duplicates:
        raise DelegationContractError(f"workers already exist: {duplicates}")
    if len(run.workers) + len(registrations) > run.budget.max_total_workers:
        raise DelegationContractError("max_total_workers exceeded")
    if any(registration.spawn_depth > run.budget.max_spawn_depth for registration in registrations):
        raise DelegationContractError("max_spawn_depth exceeded")
    workers = tuple(
        Worker(registration.worker_id, registration.backend, registration.spawn_depth)
        for registration in registrations
    )
    return replace(run, workers=(*run.workers, *workers))


def register_workers(
    path: Path,
    registrations: Sequence[WorkerRegistration],
    *,
    persist: bool = True,
) -> None:
    with _locked(path):
        run = load_run(path)
        updated = _with_registered_workers(run, registrations)
        if persist:
            save_run(path, updated)


def register_worker(path: Path, registration: WorkerRegistration) -> None:
    register_workers(path, (registration,))


def unregister_workers(path: Path, worker_ids: Sequence[WorkerId]) -> None:
    with _locked(path):
        run = load_run(path)
        requested = tuple(worker_ids)
        if len(set(requested)) != len(requested):
            raise DelegationContractError("worker ids must be unique")
        known = {worker.worker_id: worker for worker in run.workers}
        missing = sorted(str(worker_id) for worker_id in requested if worker_id not in known)
        if missing:
            raise DelegationContractError(f"unknown workers: {missing}")
        invalid = sorted(
            str(worker_id)
            for worker_id in requested
            if known[worker_id].status is not WorkerStatus.REGISTERED
        )
        if invalid:
            raise DelegationContractError(f"workers are not registered: {invalid}")
        assigned = {
            WorkerId(worker_id)
            for wave in run.waves
            for worker_id in _wave_worker_ids(wave)
        }
        wave_workers = sorted(str(worker_id) for worker_id in requested if worker_id in assigned)
        if wave_workers:
            raise DelegationContractError(f"workers assigned to a wave cannot be unregistered: {wave_workers}")
        requested_set = set(requested)
        save_run(path, replace(run, workers=tuple(worker for worker in run.workers if worker.worker_id not in requested_set)))


def release_workers(path: Path, worker_ids: Sequence[WorkerId]) -> None:
    with _locked(path):
        run = load_run(path)
        requested = tuple(worker_ids)
        if len(set(requested)) != len(requested):
            raise DelegationContractError("worker ids must be unique")
        known = {worker.worker_id: worker for worker in run.workers}
        missing = sorted(str(worker_id) for worker_id in requested if worker_id not in known)
        if missing:
            raise DelegationContractError(f"unknown workers: {missing}")
        invalid = sorted(
            str(worker_id)
            for worker_id in requested
            if known[worker_id].status is not WorkerStatus.LAUNCHED
        )
        if invalid:
            raise DelegationContractError(f"workers are not launched: {invalid}")
        requested_set = set(requested)
        workers = tuple(
            replace(worker, status=WorkerStatus.REGISTERED) if worker.worker_id in requested_set else worker
            for worker in run.workers
        )
        save_run(path, replace(run, workers=workers))


def _wave_worker_ids(wave: JsonObject) -> tuple[str, ...]:
    required = wave.get("required_worker_ids")
    if not isinstance(required, list):
        return ()
    return tuple(worker_id for worker_id in required if isinstance(worker_id, str))


def launch_workers(path: Path, worker_ids: Sequence[WorkerId], *, persist: bool = True) -> None:
    with _locked(path):
        run = load_run(path)
        requested = tuple(dict.fromkeys(worker_ids))
        if len(requested) != len(worker_ids):
            raise DelegationContractError("launch worker ids must be unique")
        assigned = {
            WorkerId(worker_id)
            for wave in run.waves
            for worker_id in _wave_worker_ids(wave)
        }
        wave_workers = sorted(str(worker_id) for worker_id in requested if worker_id in assigned)
        if wave_workers:
            raise DelegationContractError(f"workers assigned to a wave require open-wave: {wave_workers}")
        updated = reserve_registered_workers(run, requested)
        if persist:
            save_run(path, updated)


def finish_worker(path: Path, worker_id: WorkerId, status: WorkerStatus) -> None:
    if status not in TERMINAL_STATUSES:
        raise DelegationContractError("finish status must be terminal")
    with _locked(path):
        run = load_run(path)
        target = next((worker for worker in run.workers if worker.worker_id == worker_id), None)
        if target is None:
            raise DelegationContractError(f"unknown worker: {worker_id}")
        if target.status is not WorkerStatus.LAUNCHED:
            raise DelegationContractError(f"worker is not launched: {worker_id}")
        if any(
            isinstance(required, list) and worker_id in required
            for wave in run.waves
            if (required := wave.get("required_worker_ids")) is not None
        ):
            raise DelegationContractError("wave workers require a terminal receipt")
        workers = tuple(replace(worker, status=status) if worker.worker_id == worker_id else worker for worker in run.workers)
        save_run(path, replace(run, workers=workers))


def start_round(path: Path, round_id: str) -> None:
    with _locked(path):
        run = load_run(path)
        if round_id in run.rounds_started:
            raise DelegationContractError(f"round already exists: {round_id}")
        if len(run.rounds_started) >= run.budget.max_rounds:
            raise DelegationContractError("max_rounds exceeded")
        save_run(path, replace(run, rounds_started=(*run.rounds_started, round_id)))


def cancel_round(path: Path, round_id: str) -> None:
    with _locked(path):
        run = load_run(path)
        if not run.rounds_started or run.rounds_started[-1] != round_id:
            raise DelegationContractError(f"round is not latest: {round_id}")
        save_run(path, replace(run, rounds_started=run.rounds_started[:-1]))


def add_execution_wave(
    path: Path,
    wave_id: WaveId,
    worker_ids: tuple[WorkerId, ...],
    dependencies: tuple[WaveId, ...],
) -> None:
    with _locked(path):
        save_run(path, add_wave(load_run(path), wave_id, worker_ids, dependencies))


def open_execution_wave(path: Path, wave_id: WaveId) -> None:
    with _locked(path):
        save_run(path, open_wave(load_run(path), wave_id))


def record_terminal_receipt(path: Path, request: TerminalReceiptRequest) -> None:
    with _locked(path):
        save_run(path, record_terminal(load_run(path), request))


def _embedded_fan_in(run: DelegationRun, wave_id: WaveId) -> JsonObject | None:
    wave = next((item for item in run.waves if item.get("wave_id") == wave_id), None)
    if wave is None:
        raise DelegationContractError(f"unknown wave: {wave_id}")
    receipt_id = wave.get("fan_in_receipt_id")
    if receipt_id is None:
        if wave.get("status") in {"passed", "failed", "blocked"}:
            raise DelegationContractError(f"closed wave is missing fan-in receipt: {wave_id}")
        return None
    matches = [
        receipt
        for receipt in run.receipts
        if receipt.get("receipt_type") == "fan_in" and receipt.get("receipt_id") == receipt_id
    ]
    if len(matches) != 1:
        raise DelegationContractError(f"wave does not reference exactly one embedded fan-in receipt: {wave_id}")
    receipt = matches[0]
    expected = (run.run_id, wave_id, wave.get("status"))
    actual = (receipt.get("run_id"), receipt.get("wave_id"), receipt.get("aggregate_status"))
    if actual != expected:
        raise DelegationContractError(f"embedded fan-in receipt does not match closed wave: {wave_id}")
    return receipt


def join_execution_wave(path: Path, wave_id: WaveId, output: Path | None) -> None:
    with _locked(path):
        run = load_run(path)
        receipt = _embedded_fan_in(run, wave_id) if output is not None else None
        if receipt is None:
            run, receipt = fan_in(run, wave_id)
            save_run(path, run)
    if output is not None:
        if output.exists():
            try:
                published = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise DelegationContractError(f"cannot read existing fan-in output {output}: {error}") from error
            if published != receipt:
                raise DelegationContractError("existing output does not match embedded fan-in receipt")
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(output)


def summary_payload(path: Path) -> JsonObject:
    run = load_run(path)
    return {
        "format": "sejong.delegation-run-summary/v0.1-draft",
        "run_id": run.run_id,
        "worker_count": len(run.workers),
        "active_worker_count": sum(worker.status is WorkerStatus.LAUNCHED for worker in run.workers),
        "wave_statuses": {str(wave.get("wave_id")): wave.get("status") for wave in run.waves},
        "terminal_receipt_count": sum(receipt.get("receipt_type") == "worker_terminal" for receipt in run.receipts),
        "fan_in_receipt_count": sum(receipt.get("receipt_type") == "fan_in" for receipt in run.receipts),
    }


def check_failures(path: Path) -> tuple[str, ...]:
    run = load_run(path)
    failures = list(run.budget.failures())
    ids = [worker.worker_id for worker in run.workers]
    if len(ids) != len(set(ids)):
        failures.append("worker ids must be unique")
    if len(run.workers) > run.budget.max_total_workers:
        failures.append("max_total_workers exceeded")
    if sum(worker.status is WorkerStatus.LAUNCHED for worker in run.workers) > run.budget.max_concurrency:
        failures.append("max_concurrency exceeded")
    if len(run.rounds_started) > run.budget.max_rounds:
        failures.append("max_rounds exceeded")
    for worker in run.workers:
        if worker.spawn_depth < 0:
            failures.append(f"worker spawn_depth must be non-negative: {worker.worker_id}")
        if worker.spawn_depth > run.budget.max_spawn_depth:
            failures.append(f"worker max_spawn_depth exceeded: {worker.worker_id}")
        if worker.budget_ref != BUDGET_REF:
            failures.append(f"worker budget_ref does not match run budget: {worker.worker_id}")
    failures.extend(wave_failures(run))
    return tuple(failures)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage backend-neutral Sejong delegation budgets and worker reservations.")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a versioned delegation run")
    init.add_argument("path", type=Path)
    init.add_argument("--run-id", required=True)
    init.add_argument("--max-total-workers", required=True, type=int)
    init.add_argument("--max-concurrency", required=True, type=int)
    init.add_argument("--max-spawn-depth", required=True, type=int)
    init.add_argument("--max-rounds", required=True, type=int)
    register = commands.add_parser("register-worker", help="Register one native or TeamExecutor worker")
    register.add_argument("path", type=Path)
    register.add_argument("--worker-id", required=True)
    register.add_argument("--backend", required=True, choices=[backend.value for backend in Backend])
    register.add_argument("--spawn-depth", required=True, type=int)
    launch = commands.add_parser("launch-workers", help="Atomically reserve concurrency for registered workers")
    launch.add_argument("path", type=Path)
    launch.add_argument("--worker-id", required=True, action="append")
    launch.add_argument("--check-only", action="store_true")
    finish = commands.add_parser("finish-worker", help="Mark a launched worker terminal")
    finish.add_argument("path", type=Path)
    finish.add_argument("--worker-id", required=True)
    finish.add_argument("--status", required=True, choices=[status.value for status in TERMINAL_STATUSES])
    round_parser = commands.add_parser("start-round", help="Consume one round from the run budget")
    round_parser.add_argument("path", type=Path)
    round_parser.add_argument("--round-id", required=True)
    wave = commands.add_parser("add-wave", help="Declare one dependency-ordered execution wave")
    wave.add_argument("path", type=Path)
    wave.add_argument("--wave-id", required=True)
    wave.add_argument("--worker-id", required=True, action="append")
    wave.add_argument("--depends-on", action="append")
    open_parser = commands.add_parser("open-wave", help="Open a ready wave and reserve its workers")
    open_parser.add_argument("path", type=Path)
    open_parser.add_argument("--wave-id", required=True)
    terminal = commands.add_parser("record-terminal", help="Append one backend-neutral terminal worker receipt")
    terminal.add_argument("path", type=Path)
    terminal.add_argument("--receipt-id", required=True)
    terminal.add_argument("--wave-id", required=True)
    terminal.add_argument("--worker-id", required=True)
    terminal.add_argument("--backend-worker-ref", required=True)
    terminal.add_argument("--worker-contract-ref", required=True)
    terminal.add_argument("--worker-output-ref", required=True)
    terminal.add_argument("--status", required=True, choices=[status.value for status in TerminalStatus])
    terminal.add_argument("--summary", required=True)
    terminal.add_argument("--evidence-ref", required=True, action="append")
    terminal.add_argument("--blocker")
    join = commands.add_parser("fan-in", help="Compute a terminal fan-in receipt for one active wave")
    join.add_argument("path", type=Path)
    join.add_argument("--wave-id", required=True)
    join.add_argument("--output", type=Path)
    summary = commands.add_parser("summary", help="Print delegation run state as JSON")
    summary.add_argument("path", type=Path)
    check = commands.add_parser("check", help="Validate a persisted delegation run")
    check.add_argument("path", type=Path)
    return parser


def _dispatch(args: argparse.Namespace) -> None:
    match args.command:
        case "init":
            initialize_run(InitRequest(args.path, args.run_id, Budget(args.max_total_workers, args.max_concurrency, args.max_spawn_depth, args.max_rounds)))
        case "register-worker":
            register_worker(args.path, WorkerRegistration(WorkerId(args.worker_id), Backend(args.backend), args.spawn_depth))
        case "launch-workers":
            launch_workers(args.path, tuple(WorkerId(worker_id) for worker_id in args.worker_id), persist=not args.check_only)
        case "finish-worker":
            finish_worker(args.path, WorkerId(args.worker_id), WorkerStatus(args.status))
        case "start-round":
            start_round(args.path, args.round_id)
        case "add-wave":
            add_execution_wave(
                args.path,
                WaveId(args.wave_id),
                tuple(WorkerId(worker_id) for worker_id in args.worker_id),
                tuple(WaveId(wave_id) for wave_id in args.depends_on or []),
            )
        case "open-wave":
            open_execution_wave(args.path, WaveId(args.wave_id))
        case "record-terminal":
            record_terminal_receipt(
                args.path,
                TerminalReceiptRequest(
                    receipt_id=ReceiptId(args.receipt_id),
                    wave_id=WaveId(args.wave_id),
                    worker_id=WorkerId(args.worker_id),
                    backend_worker_ref=args.backend_worker_ref,
                    worker_contract_ref=args.worker_contract_ref,
                    worker_output_ref=args.worker_output_ref,
                    terminal_status=TerminalStatus(args.status),
                    summary=args.summary,
                    evidence_refs=tuple(args.evidence_ref),
                    blocker=args.blocker,
                ),
            )
        case "fan-in":
            join_execution_wave(args.path, WaveId(args.wave_id), args.output)
        case "summary":
            print(json.dumps(summary_payload(args.path), indent=2, sort_keys=True))
        case "check":
            if failures := check_failures(args.path):
                raise DelegationContractError("; ".join(failures))
        case _:
            raise DelegationContractError(f"unsupported command: {args.command}")


def main() -> int:
    args = _build_parser().parse_args()
    try:
        _dispatch(args)
    except DelegationContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"ok: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
