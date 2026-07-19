#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import codex_ticket_runner as runner
from codex_ticket_test_support import RecordingProcess, execution_spec, ticket
from delegation_run_model import load_run
from discord_contract_types import ControlContractError
from discord_target_registry import ResolvedTarget


class CodexTicketDelegationTests(unittest.TestCase):
    def test_write_ticket_requires_active_team_executor_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a launched TeamExecutor worker with worktree metadata but no active lease.
            spec = execution_spec(Path(tmp), active_lease=False)
            fake = RecordingProcess()

            # When: the ticket runner validates its existing Core/TeamExecutor binding.
            with self.assertRaises(ControlContractError) as raised:
                runner.TicketRunner(fake).run(spec)

            # Then: the missing Core-owned lease blocks execution before process start.
            self.assertEqual(raised.exception.code, "lease_required")
            self.assertEqual(fake.calls, [])

    def test_write_ticket_rejects_non_array_lease_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a Core binding whose persisted lease scopes were corrupted to an object.
            spec = execution_spec(Path(tmp), active_lease=True)
            assert spec.delegation is not None
            leases_path = spec.delegation.team_run_dir / "leases.json"
            payload = json.loads(leases_path.read_text(encoding="utf-8"))
            payload["leases"][0]["scopes"] = {"docs/example.md": True}
            leases_path.write_text(json.dumps(payload), encoding="utf-8")
            fake = RecordingProcess()

            # When/Then: malformed state cannot be interpreted as an iterable scope grant.
            with self.assertRaises(ControlContractError) as raised:
                runner.TicketRunner(fake).run(spec)
            self.assertEqual(raised.exception.code, "invalid_delegation")
            self.assertEqual(fake.calls, [])

    def test_executable_write_ticket_requires_core_delegation_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a live workspace-write ticket with no Core worker or lease binding.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            spec = runner.TicketRunSpec(
                ticket=replace(ticket(), dry_run=False),
                target=ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex")),
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )
            fake = RecordingProcess()

            # When/Then: the runner refuses to invent write authority or execute.
            with self.assertRaises(ControlContractError) as raised:
                runner.TicketRunner(fake).run(spec)
            self.assertEqual(raised.exception.code, "delegation_required")
            self.assertEqual(fake.calls, [])

    def test_process_result_fans_into_existing_delegation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a Codex ticket bound to an active TeamExecutor delegation wave.
            spec = execution_spec(Path(tmp), active_lease=True)

            # When: the fixed-model process exits successfully.
            result = runner.TicketRunner(RecordingProcess()).run(spec)

            # Then: Core receives evidence through its existing worker terminal receipt.
            assert spec.delegation is not None
            delegation = load_run(spec.delegation.delegation_run_path)
            terminal = next(item for item in delegation.receipts if item["receipt_type"] == "worker_terminal")
            self.assertEqual(terminal["worker_id"], spec.delegation.worker_id)
            self.assertEqual(terminal["worker_output_ref"], str(result.receipt_path))
            self.assertEqual(terminal["authority"], "evidence_only")

    def test_non_success_process_states_fan_in_with_blocker_disposition(self) -> None:
        cases = (
            (runner.ProcessStatus.FAILED, "failed"),
            (runner.ProcessStatus.TIMED_OUT, "timed_out"),
            (runner.ProcessStatus.CANCELLED, "blocked"),
        )
        for process_status, terminal_status in cases:
            with self.subTest(process_status=process_status), tempfile.TemporaryDirectory() as tmp:
                # Given: an active Core worker whose process ends without success.
                spec = execution_spec(Path(tmp), active_lease=True)

                # When: the ticket runner receipts the terminal process state.
                runner.TicketRunner(RecordingProcess(status=process_status)).run(spec)

                # Then: Core receives a non-success receipt with an explicit blocker.
                assert spec.delegation is not None
                delegation = load_run(spec.delegation.delegation_run_path)
                terminal = next(item for item in delegation.receipts if item["receipt_type"] == "worker_terminal")
                self.assertEqual(terminal["terminal_status"], terminal_status)
                self.assertTrue(terminal["blocker"])

    def test_prestart_cancellation_closes_bound_core_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a bound worker whose cancellation marker predates process launch.
            spec = execution_spec(Path(tmp), active_lease=True)
            spec.cancellation_path.parent.mkdir(parents=True)
            spec.cancellation_path.write_text("cancelled\n", encoding="utf-8")

            # When: the runner observes cancellation before invoking its process adapter.
            runner.TicketRunner(RecordingProcess()).run(spec)

            # Then: the existing Core worker is terminally blocked instead of left active.
            assert spec.delegation is not None
            delegation = load_run(spec.delegation.delegation_run_path)
            terminal = next(item for item in delegation.receipts if item["receipt_type"] == "worker_terminal")
            self.assertEqual(terminal["terminal_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
