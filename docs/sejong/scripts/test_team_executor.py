#!/usr/bin/env python3
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
