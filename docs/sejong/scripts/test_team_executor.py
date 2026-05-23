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


if __name__ == "__main__":
    unittest.main()
