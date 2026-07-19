#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
import json
from dataclasses import replace
from pathlib import Path

import codex_process_contract as process
import codex_ticket_runner as runner
from discord_contract_types import SandboxMode, TicketIntent
from discord_contract_types import ControlContractError
from discord_target_registry import ResolvedTarget
from codex_ticket_test_support import RecordingProcess, ticket


def direct_read_ticket() -> TicketIntent:
    return replace(ticket(), dry_run=False, sandbox=SandboxMode.READ_ONLY, write_paths=())


class CodexTicketRunnerTests(unittest.TestCase):
    def test_builds_structured_fixed_model_argv_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a parsed ticket, sealed target mapping, and selected workspace.
            workspace = Path(tmp) / "worktree"
            workspace.mkdir()
            target = ResolvedTarget(
                host_id="mac-studio",
                repo_id="king-sejong",
                repo_root=Path(tmp) / "repo",
                codex_binary=Path("/opt/homebrew/bin/codex"),
            )

            # When: Core builds the one-process launch request.
            request = process.build_codex_process(ticket(), target, workspace)

            # Then: model and sandbox are immutable argv elements and the prompt stays on stdin.
            self.assertEqual(request.argv[0], "/opt/homebrew/bin/codex")
            self.assertEqual(request.argv.count("gpt-5.4"), 1)
            self.assertEqual(request.argv[request.argv.index("--sandbox") + 1], "workspace-write")
            self.assertEqual(request.argv[-1], "-")
            self.assertNotIn("sh", request.argv)
            self.assertEqual(request.cwd, workspace)
            self.assertEqual(request.stdin_text, ticket().objective)

    def test_dry_run_writes_plan_without_invoking_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a dry-run ticket and a process fake that records calls.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            target = ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex"))
            fake = RecordingProcess()
            spec = runner.TicketRunSpec(
                ticket=ticket(),
                target=target,
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )

            # When: the runner receives the dry-run ticket.
            result = runner.TicketRunner(fake).run(spec)

            # Then: Core persists a bounded plan and never invokes a Codex process.
            self.assertEqual(result.status, runner.TicketRunStatus.DRY_RUN)
            self.assertEqual(fake.calls, [])
            self.assertTrue(result.receipt_path.is_file())
            self.assertTrue(result.receipt_path.is_relative_to(spec.run_dir))

    def test_process_result_is_bounded_and_remains_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an executable ticket and a fake returning oversized stdout.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            target = ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex"))
            fake = RecordingProcess(stdout="x" * (process.DEFAULT_OUTPUT_LIMIT_BYTES + 100))
            spec = runner.TicketRunSpec(
                ticket=direct_read_ticket(),
                target=target,
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )

            # When: the runner consumes the fake terminal result.
            result = runner.TicketRunner(fake).run(spec)

            # Then: output is capped and exit zero is recorded as evidence, not completion.
            payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, runner.TicketRunStatus.PROCESS_COMPLETED)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(fake.calls[0].model, "gpt-5.4")
            self.assertLessEqual(len(payload["result"]["stdout"].encode()), process.DEFAULT_OUTPUT_LIMIT_BYTES)
            self.assertTrue(payload["result"]["truncated"])
            self.assertEqual(payload["completion_authority"], "evidence_only")

    def test_preexisting_cancellation_prevents_process_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a non-dry ticket whose Core cancellation marker already exists.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            spec = runner.TicketRunSpec(
                ticket=direct_read_ticket(),
                target=ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex")),
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )
            spec.cancellation_path.parent.mkdir(parents=True)
            spec.cancellation_path.write_text("cancelled\n", encoding="utf-8")
            fake = RecordingProcess()

            # When: the runner checks cancellation before spawning.
            result = runner.TicketRunner(fake).run(spec)

            # Then: no process starts and the cancellation is durably receipted.
            self.assertEqual(result.status, runner.TicketRunStatus.CANCELLED)
            self.assertEqual(fake.calls, [])

    def test_timeout_is_terminal_but_never_completion_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an executable ticket whose process fake reports a timeout.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            spec = runner.TicketRunSpec(
                ticket=direct_read_ticket(),
                target=ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex")),
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )
            fake = RecordingProcess(status=runner.ProcessStatus.TIMED_OUT)

            # When: the runner receipts the terminal process state.
            result = runner.TicketRunner(fake).run(spec)

            # Then: timeout is explicit and cannot be promoted to completion.
            payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(result.status, runner.TicketRunStatus.TIMED_OUT)
            self.assertFalse(payload["completion_eligible"])

    def test_ticket_run_receipt_is_immutable_before_duplicate_process_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: one completed read-only ticket process and its sealed receipt.
            root = Path(tmp)
            workspace = root / "worktree"
            workspace.mkdir()
            spec = runner.TicketRunSpec(
                ticket=direct_read_ticket(),
                target=ResolvedTarget("mac-studio", "king-sejong", root / "repo", Path("/bin/codex")),
                workspace=workspace,
                sejong_home=root / "sejong",
                delegation=None,
            )
            fake = RecordingProcess(stdout="first")
            first = runner.TicketRunner(fake).run(spec)
            sealed = first.receipt_path.read_bytes()

            # When/Then: a duplicate attempt is rejected before another process starts.
            with self.assertRaises(ControlContractError) as raised:
                runner.TicketRunner(fake).run(spec)
            self.assertEqual(raised.exception.code, "immutable_receipt_exists")
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(first.receipt_path.read_bytes(), sealed)


if __name__ == "__main__":
    unittest.main()
