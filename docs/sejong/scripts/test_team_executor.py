#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import team_executor as team_executor_module


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
TEAM_EXECUTOR = SEJONG_ROOT / "scripts" / "team_executor.py"
DELEGATION_RUN = SEJONG_ROOT / "scripts" / "delegation_run.py"
FIXTURE_ROOT = SEJONG_ROOT / "examples" / "team-executor"


def run_check(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEAM_EXECUTOR), "check", str(FIXTURE_ROOT / name)],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


def run_team_command(
    args: list[str],
    *,
    sejong_home: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SEJONG_HOME": str(sejong_home), **(env_overrides or {})}
    return subprocess.run(
        [sys.executable, str(TEAM_EXECUTOR), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def init_delegation_run(path: Path, *, total: int, concurrency: int, rounds: int = 2) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(DELEGATION_RUN),
            "init",
            str(path),
            "--run-id",
            "team-budget",
            "--max-total-workers",
            str(total),
            "--max-concurrency",
            str(concurrency),
            "--max-spawn-depth",
            "1",
            "--max-rounds",
            str(rounds),
        ],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "sejong@example.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "King Sejong Tests"], cwd=path, check=True)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, text=True, capture_output=True, check=True)


class TeamExecutorAuthorityTests(unittest.TestCase):
    def test_valid_context_fixture_passes(self) -> None:
        result = run_check("valid-context")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_context_metadata_fails(self) -> None:
        result = run_check("invalid-missing-context")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("active_context_id", result.stderr)

    def test_worker_gate_claim_fails(self) -> None:
        result = run_check("invalid-worker-gate-claim")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worker message claims gate or final authority", result.stderr)

    def test_worker_majority_decision_fails(self) -> None:
        result = run_check("invalid-majority-decision")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worker message claims gate or final authority", result.stderr)

    def test_nested_path_lease_conflict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "lease-overlap",
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "a:implementer:docs",
                    "--worker",
                    "b:implementer:router",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "lease-overlap"

            first = run_team_command(
                ["acquire-lease", str(run_dir), "--worker-id", "a", "--scope", "docs/sejong"],
                sejong_home=sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_team_command(
                ["acquire-lease", str(run_dir), "--worker-id", "b", "--scope", "docs/sejong/ROUTER.md"],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("lease conflict", second.stderr)

    def test_glob_lease_conflict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "lease-glob",
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "a:implementer:docs",
                    "--worker",
                    "b:implementer:router",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "lease-glob"

            first = run_team_command(
                ["acquire-lease", str(run_dir), "--worker-id", "a", "--scope", "docs/sejong/*.md"],
                sejong_home=sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = run_team_command(
                ["acquire-lease", str(run_dir), "--worker-id", "b", "--scope", "docs/sejong/ROUTER.md"],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("lease conflict", second.stderr)

    def test_missing_current_surface_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "missing-surface",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "missing-surface"
            team_path = run_dir / "team.json"
            team = json.loads(team_path.read_text(encoding="utf-8"))
            del team["current_surface"]
            team_path.write_text(json.dumps(team, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = run_team_command(["check", str(run_dir)], sejong_home=sejong_home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("current_surface", result.stderr)

    def test_message_role_scope_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "message-mismatch",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "message-mismatch"
            opened = run_team_command(
                ["open-round", str(run_dir), "--purpose", "first challenge"],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)

            result = run_team_command(
                [
                    "append-message",
                    str(run_dir),
                    "--worker-id",
                    "critic",
                    "--role",
                    "advocate",
                    "--kind",
                    "claim",
                    "--summary",
                    "Mismatched role.",
                ],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("message role does not match", result.stderr)

    def test_send_and_receive_versioned_peer_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "peer-envelope",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                    "--worker",
                    "advocate:advocate:bounded option review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "peer-envelope"
            opened = run_team_command(
                ["open-round", str(run_dir), "--purpose", "peer challenge"],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)

            sent = run_team_command(
                [
                    "send-message",
                    str(run_dir),
                    "--message-id",
                    "m-peer-1",
                    "--worker-id",
                    "critic",
                    "--kind",
                    "question",
                    "--recipient",
                    "worker:advocate",
                    "--summary",
                    "Can you answer this bounded objection?",
                    "--requires-response",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(sent.returncode, 0, sent.stderr)

            received = run_team_command(
                ["receive-messages", str(run_dir), "--worker-id", "advocate"],
                sejong_home=sejong_home,
            )
            self.assertEqual(received.returncode, 0, received.stderr)
            payload = json.loads(received.stdout)
            self.assertEqual(payload["format"], "sejong.team-mailbox-receive/v0.1-draft")
            self.assertEqual(payload["count"], 1)
            message = payload["messages"][0]
            self.assertEqual(message["format"], "sejong.team-mailbox-message/v0.1-draft")
            self.assertEqual(message["direction"], "worker_to_worker")
            self.assertEqual(message["sender"]["id"], "critic")
            self.assertEqual(message["recipients"][0]["id"], "advocate")
            self.assertTrue(message["requires_response"])

    def test_send_message_rejects_duplicate_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "duplicate-message-id",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "duplicate-message-id"
            opened = run_team_command(["open-round", str(run_dir), "--purpose", "duplicate id test"], sejong_home=sejong_home)
            self.assertEqual(opened.returncode, 0, opened.stderr)

            first = run_team_command(
                [
                    "send-message",
                    str(run_dir),
                    "--message-id",
                    "m-duplicate",
                    "--worker-id",
                    "critic",
                    "--kind",
                    "claim",
                    "--summary",
                    "First message.",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            duplicate = run_team_command(
                [
                    "send-message",
                    str(run_dir),
                    "--message-id",
                    "m-duplicate",
                    "--worker-id",
                    "critic",
                    "--kind",
                    "claim",
                    "--summary",
                    "Duplicate message.",
                ],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("duplicate message_id", duplicate.stderr)

    def test_send_message_generates_non_positional_message_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "generated-message-id",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "generated-message-id"
            opened = run_team_command(["open-round", str(run_dir), "--purpose", "id generation test"], sejong_home=sejong_home)
            self.assertEqual(opened.returncode, 0, opened.stderr)

            sent = run_team_command(
                [
                    "send-message",
                    str(run_dir),
                    "--worker-id",
                    "critic",
                    "--kind",
                    "claim",
                    "--summary",
                    "Generated id message.",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(sent.returncode, 0, sent.stderr)

            messages = [
                json.loads(line)
                for line in (run_dir / "mailbox.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(messages), 1)
            self.assertTrue(str(messages[0]["message_id"]).startswith("msg-"))
            self.assertNotEqual(messages[0]["message_id"], "round-1-critic-1")

    def test_send_message_rejects_unresolvable_evidence_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "message-evidence-ref",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "message-evidence-ref"
            opened = run_team_command(["open-round", str(run_dir), "--purpose", "evidence ref test"], sejong_home=sejong_home)
            self.assertEqual(opened.returncode, 0, opened.stderr)

            result = run_team_command(
                [
                    "send-message",
                    str(run_dir),
                    "--worker-id",
                    "critic",
                    "--kind",
                    "claim",
                    "--summary",
                    "Missing evidence.",
                    "--evidence-ref",
                    "missing-evidence.md",
                ],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("evidence_ref does not exist", result.stderr)

    def test_acquire_lease_rejects_duplicate_lease_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "duplicate-lease-id",
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "a:implementer:docs",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "duplicate-lease-id"

            first = run_team_command(
                ["acquire-lease", str(run_dir), "--lease-id", "lease-duplicate", "--worker-id", "a", "--scope", "docs/a.md"],
                sejong_home=sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            duplicate = run_team_command(
                ["acquire-lease", str(run_dir), "--lease-id", "lease-duplicate", "--worker-id", "a", "--scope", "docs/b.md"],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("duplicate lease_id", duplicate.stderr)

    def test_persuasion_round_is_bounded_to_thirty_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "persuasion-cap",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "ux:ux:UX perspective",
                    "--worker",
                    "risk:risk:Risk perspective",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "persuasion-cap"

            result = run_team_command(
                [
                    "open-round",
                    str(run_dir),
                    "--round-id",
                    "persuade-1",
                    "--purpose",
                    "persuade opposing perspectives before lead synthesis",
                    "--round-kind",
                    "persuasion",
                    "--max-duration-minutes",
                    "45",
                ],
                sejong_home=sejong_home,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("persuasion rounds are capped at 30 minutes", result.stderr)

    def test_persuasion_round_records_closure_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "persuasion-close",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "architect:architect:architecture perspective",
                    "--worker",
                    "critic:critic:devil advocate perspective",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "persuasion-close"
            opened = run_team_command(
                [
                    "open-round",
                    str(run_dir),
                    "--round-id",
                    "persuade-1",
                    "--purpose",
                    "mutual persuasion before lead synthesis",
                    "--round-kind",
                    "persuasion",
                    "--max-duration-minutes",
                    "30",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)

            closed = run_team_command(
                ["close-round", str(run_dir), "persuade-1", "--closed-reason", "apparent_convergence"],
                sejong_home=sejong_home,
            )
            self.assertEqual(closed.returncode, 0, closed.stderr)
            rounds = json.loads((run_dir / "rounds.json").read_text(encoding="utf-8"))
            round_record = rounds["rounds"][0]
            self.assertEqual(round_record["round_kind"], "persuasion")
            self.assertEqual(round_record["max_duration_minutes"], 30)
            self.assertEqual(round_record["closure_policy"], "lead_synthesis_after_convergence_or_30m_deadlock")
            self.assertEqual(round_record["closed_reason"], "apparent_convergence")

    def test_launch_injects_surface_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "launch-context",
                    "--current-surface",
                    "uigwe",
                    "--worker",
                    "ready:readiness-checker:plan readiness",
                    "--command",
                    "ready=echo ready",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "launch-context"

            result = run_team_command(["launch", str(run_dir), "--dry-run"], sejong_home=sejong_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SEJONG_CURRENT_SURFACE=uigwe", result.stdout)
            self.assertIn("SEJONG_WORKER_ROLE=readiness-checker", result.stdout)

    def test_worker_state_records_complete_prompt_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "prompt-state",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--source-of-truth-ref",
                    "brief.md",
                    "--source-of-truth-ref",
                    "docs/sejong/TEAM_EXECUTOR.md",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "prompt-state"
            state = json.loads((run_dir / "workers" / "critic" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_surface"], "jiphyeonjeon")
            self.assertIn("objective", state)
            self.assertEqual(state["role"], "critic")
            self.assertEqual(state["scope"], "bounded risk review")
            self.assertEqual(state["source_of_truth_refs"], ["brief.md", "docs/sejong/TEAM_EXECUTOR.md"])
            self.assertIn("write_scope", state)
            self.assertIn("evidence_refs", state)
            self.assertIn("prompt_path", state)
            self.assertIn("return_format", state)
            self.assertIn("forbidden_worker_claims", state)
            self.assertIn("verification_expectation", state)
            prompt = (run_dir / state["prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("You are a bounded Jiphyeonjeon worker", prompt)
            self.assertIn("Objective:", prompt)
            self.assertIn("Role: critic", prompt)
            self.assertIn("Source of truth refs:", prompt)
            self.assertIn("Write scope:", prompt)
            self.assertIn("Evidence refs:", prompt)
            self.assertIn("Forbidden claims:", prompt)

    def test_check_fails_when_worker_prompt_contract_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "missing-prompt-contract",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "missing-prompt-contract"
            team_path = run_dir / "team.json"
            team = json.loads(team_path.read_text(encoding="utf-8"))
            del team["workers"][0]["write_scope"]
            team_path.write_text(json.dumps(team, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = run_team_command(["check", str(run_dir)], sejong_home=sejong_home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("worker missing write_scope", result.stderr)
            self.assertIn("worker brief critic write_scope must be a non-empty list", result.stderr)

    def test_launch_injects_complete_worker_prompt_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "launch-prompt",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "critic:critic:bounded risk review",
                    "--command",
                    "critic=codex exec -",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "launch-prompt"

            result = run_team_command(["launch", str(run_dir), "--dry-run"], sejong_home=sejong_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SEJONG_CURRENT_SURFACE=jiphyeonjeon", result.stdout)
            self.assertIn("SEJONG_WORKER_ROLE=critic", result.stdout)
            self.assertIn("SEJONG_WORKER_OBJECTIVE=", result.stdout)
            self.assertIn("SEJONG_WORKER_SCOPE='bounded risk review'", result.stdout)
            self.assertIn("SEJONG_WORKER_ALLOWED_OUTPUTS=", result.stdout)
            self.assertIn("SEJONG_WORKER_WRITE_SCOPE=", result.stdout)
            self.assertIn("SEJONG_WORKER_EVIDENCE_REFS=", result.stdout)
            self.assertIn("SEJONG_WORKER_VERIFICATION_EXPECTATION=", result.stdout)
            self.assertIn("SEJONG_FORBIDDEN_WORKER_CLAIMS=", result.stdout)
            self.assertIn("SEJONG_WORKER_RETURN_FORMAT=", result.stdout)
            self.assertIn("< ", result.stdout)
            self.assertIn("workers/critic/prompt.md", result.stdout)

    def test_prepare_workspaces_creates_only_for_write_capable_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            init_git_repo(repo_root)
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "prepare-isolation",
                    "--repo-root",
                    str(repo_root),
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "writer:executor:implementation",
                    "--worker",
                    "reader:critic:review",
                    "--worker-write-scope",
                    "writer=docs/example.md",
                    "--worker-write-scope",
                    "reader=none",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "prepare-isolation"
            lease = run_team_command(
                ["acquire-lease", str(run_dir), "--lease-id", "lease-writer-docs", "--worker-id", "writer", "--scope", "docs/example.md"],
                sejong_home=sejong_home,
            )
            self.assertEqual(lease.returncode, 0, lease.stderr)

            prepared = run_team_command(["prepare-workspaces", str(run_dir)], sejong_home=sejong_home)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            writer_state = json.loads((run_dir / "workers" / "writer" / "state.json").read_text(encoding="utf-8"))
            reader_state = json.loads((run_dir / "workers" / "reader" / "state.json").read_text(encoding="utf-8"))

            isolation = writer_state["isolation"]
            self.assertEqual(isolation["backend"], "worktree")
            self.assertEqual(isolation["cleanup_status"], "active")
            self.assertEqual(isolation["dirty_status"], "clean")
            self.assertEqual(isolation["lease_refs"], ["lease-writer-docs"])
            self.assertTrue(Path(isolation["workspace_path"]).exists())
            self.assertNotIn("isolation", reader_state)

    def test_launch_dry_run_uses_isolated_worker_cwd_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            init_git_repo(repo_root)
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "launch-isolation",
                    "--repo-root",
                    str(repo_root),
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "writer:executor:implementation",
                    "--worker-write-scope",
                    "writer=docs/example.md",
                    "--command",
                    "writer=echo writer",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "launch-isolation"
            prepared = run_team_command(["prepare-workspaces", str(run_dir)], sejong_home=sejong_home)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            state = json.loads((run_dir / "workers" / "writer" / "state.json").read_text(encoding="utf-8"))
            workspace = state["isolation"]["workspace_path"]

            result = run_team_command(["launch", str(run_dir), "--dry-run"], sejong_home=sejong_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"-c {workspace}", result.stdout)
            self.assertIn("SEJONG_WORKER_ISOLATION_BACKEND=worktree", result.stdout)
            self.assertIn(f"SEJONG_WORKER_WORKSPACE={workspace}", result.stdout)

    def test_isolate_write_workers_does_not_force_read_only_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            init_git_repo(repo_root)
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "read-only-no-worktree",
                    "--repo-root",
                    str(repo_root),
                    "--current-surface",
                    "jiphyeonjeon",
                    "--worker",
                    "reader:critic:review",
                    "--worker-write-scope",
                    "reader=none",
                    "--command",
                    "reader=echo reader",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "read-only-no-worktree"

            result = run_team_command(["launch", str(run_dir), "--dry-run", "--isolate-write-workers"], sejong_home=sejong_home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"-c {repo_root.resolve()}", result.stdout)
            self.assertIn("SEJONG_WORKER_ISOLATION_BACKEND=none", result.stdout)
            self.assertFalse((run_dir / "workspaces" / "reader").exists())

    def test_launch_blocks_when_worktree_creation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            non_git_root = root / "not-git"
            non_git_root.mkdir()
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "worktree-failure",
                    "--repo-root",
                    str(non_git_root),
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "writer:executor:implementation",
                    "--worker-write-scope",
                    "writer=docs/example.md",
                    "--command",
                    "writer=echo writer",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "worktree-failure"

            result = run_team_command(["launch", str(run_dir), "--isolate-write-workers"], sejong_home=sejong_home)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("failed to create worker worktree", result.stderr)

    def test_cleanup_preserves_dirty_isolated_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            init_git_repo(repo_root)
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "dirty-preserve",
                    "--repo-root",
                    str(repo_root),
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "writer:executor:implementation",
                    "--worker-write-scope",
                    "writer=docs/example.md",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "dirty-preserve"
            prepared = run_team_command(["prepare-workspaces", str(run_dir)], sejong_home=sejong_home)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            state = json.loads((run_dir / "workers" / "writer" / "state.json").read_text(encoding="utf-8"))
            workspace = Path(state["isolation"]["workspace_path"])
            (workspace / "untracked.txt").write_text("keep me\n", encoding="utf-8")

            cleanup = run_team_command(["cleanup-workspaces", str(run_dir)], sejong_home=sejong_home)
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            updated = json.loads((run_dir / "workers" / "writer" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["isolation"]["dirty_status"], "dirty")
            self.assertEqual(updated["isolation"]["cleanup_status"], "preserved_dirty")
            self.assertTrue(workspace.exists())

    def test_live_smoke_records_tmux_worker_cwd_env_and_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            init_git_repo(repo_root)
            sejong_home = root / "sejong"
            init = run_team_command(
                [
                    "init",
                    "--run-id",
                    "live-smoke",
                    "--repo-root",
                    str(repo_root),
                    "--current-surface",
                    "seungjeongwon",
                    "--worker",
                    "writer:executor:implementation",
                    "--worker-write-scope",
                    "writer=docs/example.md",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            run_dir = sejong_home / "state" / "team" / "live-smoke"
            lease = run_team_command(
                ["acquire-lease", str(run_dir), "--lease-id", "lease-writer-docs", "--worker-id", "writer", "--scope", "docs/example.md"],
                sejong_home=sejong_home,
            )
            self.assertEqual(lease.returncode, 0, lease.stderr)

            smoke = run_team_command(
                ["smoke-live-launch", str(run_dir), "--worker-id", "writer", "--isolate-write-workers", "--timeout-seconds", "10"],
                sejong_home=sejong_home,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            payload = json.loads(smoke.stdout)
            if payload["status"] == "skipped":
                self.assertEqual(payload["reason"], "tmux unavailable")
                return
            self.assertEqual(payload["status"], "passed")
            self.assertFalse(payload["session_remaining"])
            evidence_path = Path(payload["evidence_path"])
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            state = json.loads((run_dir / "workers" / "writer" / "state.json").read_text(encoding="utf-8"))
            workspace = state["isolation"]["workspace_path"]
            self.assertEqual(evidence["cwd"], workspace)
            self.assertEqual(evidence["env"]["SEJONG_WORKER_ISOLATION_BACKEND"], "worktree")
            self.assertEqual(evidence["env"]["SEJONG_WORKER_WORKSPACE"], workspace)
            self.assertEqual(json.loads(evidence["env"]["SEJONG_WORKER_ISOLATION_LEASE_REFS"]), ["lease-writer-docs"])
            self.assertGreater(evidence["stdin_bytes"], 0)

    def test_sandbox_claim_guard_allows_negated_warning_and_rejects_positive_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "allowed.md"
            allowed.write_text("A git worktree is edit isolation only; it is not process sandboxing.\n", encoding="utf-8")
            rejected = root / "rejected.md"
            rejected.write_text("TeamExecutor worktrees provide process sandboxing for workers.\n", encoding="utf-8")

            ok = run_team_command(["check-sandbox-claims", str(allowed)], sejong_home=root / "sejong")
            self.assertEqual(ok.returncode, 0, ok.stderr)

            bad = run_team_command(["check-sandbox-claims", str(rejected)], sejong_home=root / "sejong")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("worktree sandbox overclaim", bad.stderr)

    def test_delegation_budget_registers_team_workers_with_shared_reference(self) -> None:
        # Given: a caller-owned delegation budget with one worker slot.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)

            # When: TeamExecutor initializes one bounded worker against that run.
            result = run_team_command(
                [
                    "init",
                    "--run-id",
                    "budget-linked",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                    "--worker",
                    "implementer:executor:bounded change",
                ],
                sejong_home=root / "sejong",
            )

            # Then: team and worker records carry the same generic budget reference.
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = root / "sejong" / "state" / "team" / "budget-linked"
            team = json.loads((run_dir / "team.json").read_text(encoding="utf-8"))
            worker = team["workers"][0]
            self.assertEqual(team["delegation_run_ref"], str(delegation_path.resolve()))
            self.assertEqual(team["budget_ref"], "#/budget")
            self.assertEqual(worker["backend"], "team_executor")
            self.assertEqual(worker["budget_ref"], "#/budget")

    def test_delegation_budget_rejects_team_worker_registration_overflow(self) -> None:
        # Given: a caller-owned delegation budget with one total worker slot.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)

            # When: TeamExecutor tries to initialize two workers.
            result = run_team_command(
                [
                    "init",
                    "--run-id",
                    "budget-overflow",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                    "--worker",
                    "worker-a:executor:first",
                    "--worker",
                    "worker-b:executor:second",
                ],
                sejong_home=root / "sejong",
            )

            # Then: the generic total-worker cap blocks the second registration.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_total_workers exceeded", result.stderr)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["workers"], [])
            self.assertFalse((root / "sejong" / "state" / "team" / "budget-overflow").exists())

    def test_delegation_budget_add_worker_local_failure_does_not_register_worker(self) -> None:
        # Given: a delegation-linked team whose target worker directory cannot be created.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "add-worker-failure",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "add-worker-failure"
            blocked_worker_path = run_dir / "workers" / "worker-a"
            blocked_worker_path.write_text("not a directory", encoding="utf-8")

            # When: local worker materialization fails.
            result = run_team_command(
                ["add-worker", str(run_dir), "worker-a:executor:bounded"],
                sejong_home=sejong_home,
            )

            # Then: the shared delegation budget remains unchanged.
            self.assertNotEqual(result.returncode, 0)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["workers"], [])

    def test_add_worker_save_failure_compensates_delegation_registration(self) -> None:
        # Given: a delegation-linked team and an injected local team-state write failure.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "add-worker-save-failure",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "add-worker-save-failure"

            # When: local team persistence fails after Core registration.
            with mock.patch.object(team_executor_module, "save_team", side_effect=OSError("injected save failure")):
                with self.assertRaisesRegex(OSError, "injected save failure"):
                    team_executor_module.add_worker_record(
                        run_dir,
                        {"worker_id": "worker-a", "role": "executor", "scope": "bounded"},
                    )

            # Then: Core and local worker paths both roll back.
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["workers"], [])
            self.assertFalse((run_dir / "workers" / "worker-a").exists())
            self.assertFalse((run_dir / "artifacts" / "worker-a").exists())

    def test_delegation_budget_rejects_team_launch_concurrency_overflow(self) -> None:
        # Given: two TeamExecutor workers sharing one concurrent launch slot.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=2, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "launch-overflow",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                    "--worker",
                    "worker-a:executor:first",
                    "--worker",
                    "worker-b:executor:second",
                    "--command",
                    "worker-a=echo a",
                    "--command",
                    "worker-b=echo b",
                ],
                sejong_home=root / "sejong",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = root / "sejong" / "state" / "team" / "launch-overflow"

            # When: TeamExecutor dry-runs both workers in one launch batch.
            result = run_team_command(["launch", str(run_dir), "--dry-run"], sejong_home=root / "sejong")

            # Then: the shared concurrency budget rejects the launch before tmux planning.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_concurrency exceeded", result.stderr)

    def test_delegation_budget_rejects_team_round_overflow(self) -> None:
        # Given: a TeamExecutor run sharing a one-round delegation budget.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1, rounds=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "round-overflow",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=root / "sejong",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = root / "sejong" / "state" / "team" / "round-overflow"
            self.assertEqual(
                run_team_command(["open-round", str(run_dir), "--purpose", "first"], sejong_home=root / "sejong").returncode,
                0,
            )

            # When: TeamExecutor opens a second round.
            result = run_team_command(["open-round", str(run_dir), "--purpose", "second"], sejong_home=root / "sejong")

            # Then: the shared maximum round count rejects it.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_rounds exceeded", result.stderr)

    def test_invalid_local_round_does_not_consume_delegation_round(self) -> None:
        # Given: a delegation-linked TeamExecutor run with an unused round budget.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1, rounds=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "invalid-local-round",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=root / "sejong",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = root / "sejong" / "state" / "team" / "invalid-local-round"

            # When: local persuasion-round validation rejects an overlong duration.
            result = run_team_command(
                [
                    "open-round",
                    str(run_dir),
                    "--purpose",
                    "invalid duration",
                    "--round-kind",
                    "persuasion",
                    "--max-duration-minutes",
                    "31",
                ],
                sejong_home=root / "sejong",
            )

            # Then: Core has not consumed the round.
            self.assertNotEqual(result.returncode, 0)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["rounds_started"], [])

    def test_round_write_failure_cancels_just_started_delegation_round(self) -> None:
        # Given: a valid delegation-linked round whose local write will fail.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1, rounds=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "round-write-failure",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=root / "sejong",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = root / "sejong" / "state" / "team" / "round-write-failure"
            args = Namespace(
                run_dir=str(run_dir),
                round_id=None,
                purpose="injected persistence failure",
                round_kind="challenge",
                max_duration_minutes=None,
            )

            # When: the local rounds artifact cannot be persisted.
            with mock.patch.object(team_executor_module, "write_json", side_effect=OSError("injected round failure")):
                with self.assertRaisesRegex(OSError, "injected round failure"):
                    team_executor_module.open_round(args)

            # Then: the newly consumed Core round is compensated.
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["rounds_started"], [])

    def test_open_round_serializes_a_concurrent_local_round_writer(self) -> None:
        # Given: another lock-aware writer attempts to update rounds after open-round reads local state.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            initialized = run_team_command(
                ["init", "--run-id", "round-concurrency", "--current-surface", "jiphyeonjeon"],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "round-concurrency"
            threads: list[threading.Thread] = []

            def concurrent_write() -> None:
                with team_executor_module.run_state_lock(run_dir):
                    payload = team_executor_module.load_json(team_executor_module.rounds_path(run_dir))
                    payload["rounds"].append({"round_id": "concurrent-round", "status": "open"})
                    team_executor_module.write_json(team_executor_module.rounds_path(run_dir), payload)

            def start_concurrent_write() -> str:
                thread = threading.Thread(target=concurrent_write)
                threads.append(thread)
                thread.start()
                thread.join(timeout=0.2)
                return "2026-07-11T00:00:00Z"

            args = Namespace(
                run_dir=str(run_dir),
                round_id=None,
                purpose="serialized round",
                round_kind="challenge",
                max_duration_minutes=None,
            )

            # When: TeamExecutor opens its round while the second writer races the same artifact.
            with mock.patch.object(team_executor_module, "now_utc", side_effect=start_concurrent_write):
                self.assertEqual(team_executor_module.open_round(args), 0)
            for thread in threads:
                thread.join(timeout=1)

            # Then: the lock prevents stale-snapshot overwrite and preserves both round ids.
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            rounds = team_executor_module.load_json(team_executor_module.rounds_path(run_dir))["rounds"]
            self.assertEqual([item["round_id"] for item in rounds], ["round-1", "concurrent-round"])

    def test_close_round_serializes_a_concurrent_local_round_writer(self) -> None:
        # Given: another lock-aware writer attempts to append a round after close-round reads local state.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            initialized = run_team_command(
                ["init", "--run-id", "round-close-concurrency", "--current-surface", "jiphyeonjeon"],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "round-close-concurrency"
            opened = run_team_command(
                ["open-round", str(run_dir), "--round-id", "round-1", "--purpose", "round to close"],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)
            writer_started = threading.Event()
            threads: list[threading.Thread] = []

            def concurrent_write() -> None:
                writer_started.set()
                with team_executor_module.run_state_lock(run_dir):
                    payload = team_executor_module.load_json(team_executor_module.rounds_path(run_dir))
                    payload["rounds"].append({"round_id": "concurrent-round", "status": "open"})
                    team_executor_module.write_json(team_executor_module.rounds_path(run_dir), payload)

            def start_concurrent_write() -> str:
                thread = threading.Thread(target=concurrent_write)
                threads.append(thread)
                thread.start()
                self.assertTrue(writer_started.wait(timeout=1))
                thread.join(timeout=0.2)
                return "2026-07-11T00:00:00Z"

            args = Namespace(run_dir=str(run_dir), round_id="round-1", closed_reason="completed")

            # When: TeamExecutor closes its round while the second writer races the same artifact.
            with mock.patch.object(team_executor_module, "now_utc", side_effect=start_concurrent_write):
                self.assertEqual(team_executor_module.close_round(args), 0)
            for thread in threads:
                thread.join(timeout=1)

            # Then: the lock preserves both the closure and the concurrently appended round.
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            rounds = team_executor_module.load_json(team_executor_module.rounds_path(run_dir))["rounds"]
            self.assertEqual([item["round_id"] for item in rounds], ["round-1", "concurrent-round"])
            self.assertEqual(rounds[0]["status"], "closed")
            self.assertEqual(rounds[0]["closed_at"], "2026-07-11T00:00:00Z")
            self.assertEqual(rounds[0]["closed_reason"], "completed")

    def test_open_round_rejects_preexisting_linked_core_round_drift_without_mutation(self) -> None:
        # Given: a linked run with one local round but a different persisted Core round id.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "open-round-drift",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "open-round-drift"
            opened = run_team_command(
                ["open-round", str(run_dir), "--round-id", "round-1", "--purpose", "first"],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            delegation["rounds_started"] = ["core-only-round"]
            delegation_path.write_text(json.dumps(delegation), encoding="utf-8")
            core_before = delegation_path.read_bytes()
            local_before = team_executor_module.rounds_path(run_dir).read_bytes()

            # When: another round is opened while the linked ledgers already disagree.
            result = run_team_command(
                ["open-round", str(run_dir), "--round-id", "round-2", "--purpose", "second"],
                sejong_home=sejong_home,
            )

            # Then: the command fails closed and neither state file changes by one byte.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Core round ids do not match TeamExecutor round ids", result.stderr)
            self.assertEqual(delegation_path.read_bytes(), core_before)
            self.assertEqual(team_executor_module.rounds_path(run_dir).read_bytes(), local_before)

    def test_close_round_rejects_preexisting_linked_core_round_drift_without_mutation(self) -> None:
        # Given: a linked open round whose persisted Core round id was replaced out of band.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "close-round-drift",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "close-round-drift"
            opened = run_team_command(
                ["open-round", str(run_dir), "--round-id", "round-1", "--purpose", "first"],
                sejong_home=sejong_home,
            )
            self.assertEqual(opened.returncode, 0, opened.stderr)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            delegation["rounds_started"] = ["core-only-round"]
            delegation_path.write_text(json.dumps(delegation), encoding="utf-8")
            core_before = delegation_path.read_bytes()
            local_before = team_executor_module.rounds_path(run_dir).read_bytes()

            # When: the local round is closed while the linked ledgers already disagree.
            result = run_team_command(
                ["close-round", str(run_dir), "round-1", "--closed-reason", "completed"],
                sejong_home=sejong_home,
            )

            # Then: the command fails closed and neither state file changes by one byte.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Core round ids do not match TeamExecutor round ids", result.stderr)
            self.assertEqual(delegation_path.read_bytes(), core_before)
            self.assertEqual(team_executor_module.rounds_path(run_dir).read_bytes(), local_before)

    def test_check_rejects_linked_core_round_id_drift(self) -> None:
        # Given: a linked TeamExecutor run whose local and Core round ids initially agree.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "round-drift",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--delegation-run",
                    str(delegation_path),
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            run_dir = sejong_home / "state" / "team" / "round-drift"
            self.assertEqual(
                run_team_command(["open-round", str(run_dir), "--purpose", "first"], sejong_home=sejong_home).returncode,
                0,
            )
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            delegation["rounds_started"] = ["core-only-round"]
            delegation_path.write_text(json.dumps(delegation), encoding="utf-8")

            # When: the persisted TeamExecutor run is checked.
            checked = run_team_command(["check", str(run_dir)], sejong_home=sejong_home)

            # Then: round-id drift is a validation failure rather than silent budget divergence.
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("Core round ids do not match TeamExecutor round ids", checked.stderr)

    def test_tmux_launch_failure_releases_delegation_worker_reservations(self) -> None:
        # Given: one delegation-linked worker and a tmux executable that always fails.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong"
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "launch-failure",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                    "--worker",
                    "worker-a:executor:bounded",
                    "--command",
                    "worker-a=echo ready",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_tmux = fake_bin / "tmux"
            fake_tmux.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
            fake_tmux.chmod(0o755)
            run_dir = sejong_home / "state" / "team" / "launch-failure"

            # When: the process launch fails after reservation.
            result = run_team_command(
                ["launch", str(run_dir)],
                sejong_home=sejong_home,
                env_overrides={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
            )

            # Then: the delegation worker returns to registered instead of staying launched.
            self.assertNotEqual(result.returncode, 0)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["workers"][0]["status"], "registered")

    def test_delegation_wave_workers_cannot_launch_through_team_executor(self) -> None:
        # Given: a TeamExecutor worker assigned to a declared Core wave.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            self.assertEqual(init_delegation_run(delegation_path, total=1, concurrency=1).returncode, 0)
            initialized = run_team_command(
                [
                    "init",
                    "--run-id",
                    "wave-gated",
                    "--current-surface",
                    "seungjeongwon",
                    "--delegation-run",
                    str(delegation_path),
                    "--worker",
                    "worker-a:executor:bounded",
                    "--command",
                    "worker-a=echo ready",
                ],
                sejong_home=root / "sejong",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            declared = subprocess.run(
                [
                    sys.executable,
                    str(DELEGATION_RUN),
                    "add-wave",
                    str(delegation_path),
                    "--wave-id",
                    "wave-1",
                    "--worker-id",
                    "worker-a",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(declared.returncode, 0, declared.stderr)
            run_dir = root / "sejong" / "state" / "team" / "wave-gated"

            # When: TeamExecutor attempts its normal direct launch path.
            result = run_team_command(["launch", str(run_dir), "--dry-run"], sejong_home=root / "sejong")

            # Then: Core requires open-wave and leaves the worker registered.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("assigned to a wave", result.stderr)
            delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
            self.assertEqual(delegation["workers"][0]["status"], "registered")


if __name__ == "__main__":
    unittest.main()
