#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
TEAM_EXECUTOR = SEJONG_ROOT / "scripts" / "team_executor.py"
FIXTURE_ROOT = SEJONG_ROOT / "examples" / "team-executor"


def run_check(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEAM_EXECUTOR), "check", str(FIXTURE_ROOT / name)],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


def run_team_command(args: list[str], *, sejong_home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SEJONG_HOME": str(sejong_home)}
    return subprocess.run(
        [sys.executable, str(TEAM_EXECUTOR), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
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


if __name__ == "__main__":
    unittest.main()
