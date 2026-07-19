from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import codex_process_contract as process
import codex_ticket_runner as runner
from delegation_run import add_execution_wave, initialize_run, open_execution_wave, register_worker
from delegation_run_model import Backend, Budget, InitRequest, WorkerId, WorkerRegistration
from delegation_wave import WaveId
from discord_contract_types import RiskClass, SandboxMode, TicketIntent
from discord_target_registry import ResolvedTarget


def ticket() -> TicketIntent:
    return TicketIntent(
        ticket_id="ticket-1",
        objective="Update one bounded documentation file",
        host_id="mac-studio",
        repo_id="king-sejong",
        task_class="implementation",
        risk_class=RiskClass.LOW,
        model="gpt-5.4",
        sandbox=SandboxMode.WORKSPACE_WRITE,
        timeout_seconds=900,
        read_paths=("docs",),
        write_paths=("docs/example.md",),
        verification_requirements=("git diff --check",),
        dry_run=True,
    )


class RecordingProcess:
    def __init__(
        self,
        stdout: str = "",
        status: runner.ProcessStatus = runner.ProcessStatus.COMPLETED,
    ) -> None:
        self.calls: list[process.CodexProcessRequest] = []
        self.stdout = stdout
        self.status = status

    def run(self, request: process.CodexProcessRequest, cancellation_path: Path) -> runner.ProcessResult:
        self.calls.append(request)
        exit_code = 0 if self.status is runner.ProcessStatus.COMPLETED else None
        return runner.ProcessResult(self.status, exit_code, self.stdout, "", False)


def execution_spec(root: Path, *, active_lease: bool) -> runner.TicketRunSpec:
    workspace = root / "worktree"
    workspace.mkdir()
    delegation_path = root / "sejong" / "runs" / "delegation.json"
    initialize_run(InitRequest(delegation_path, "delegation-1", Budget(1, 1, 1, 1)))
    register_worker(
        delegation_path,
        WorkerRegistration(WorkerId("worker-1"), Backend.TEAM_EXECUTOR, 1),
    )
    add_execution_wave(delegation_path, WaveId("wave-1"), (WorkerId("worker-1"),), ())
    open_execution_wave(delegation_path, WaveId("wave-1"))
    team_run = root / "sejong" / "state" / "team" / "team-1"
    team_run.mkdir(parents=True)
    (team_run / "team.json").write_text(json.dumps({
        "format": "sejong.team/v0.1-draft",
        "run_id": "team-1",
        "delegation_run_ref": str(delegation_path),
        "workers": [{
            "worker_id": "worker-1",
            "write_scope": ["docs/example.md"],
            "isolation": {
                "backend": "worktree",
                "workspace_path": str(workspace),
                "base_ref": "HEAD",
                "lease_refs": ["lease-1"],
                "dirty_status": "clean",
                "cleanup_status": "active",
            },
        }],
    }), encoding="utf-8")
    leases = [{
        "lease_id": "lease-1",
        "worker_id": "worker-1",
        "scopes": ["docs/example.md"],
        "status": "active",
        "acquired_at": "2026-07-19T10:00:00Z",
        "released_at": None,
    }] if active_lease else []
    (team_run / "leases.json").write_text(json.dumps({
        "format": "sejong.team-leases/v0.1-draft",
        "run_id": "team-1",
        "leases": leases,
    }), encoding="utf-8")
    return runner.TicketRunSpec(
        ticket=replace(ticket(), dry_run=False),
        target=ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex")),
        workspace=workspace,
        sejong_home=root / "sejong",
        delegation=runner.DelegationBinding(
            team_run_dir=team_run,
            delegation_run_path=delegation_path,
            worker_id="worker-1",
            wave_id="wave-1",
            worker_contract_ref="contract://ticket-1",
            lease_refs=("lease-1",),
        ),
    )
