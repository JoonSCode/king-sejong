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
CLEANUP = SEJONG_ROOT / "scripts" / "sejong_cleanup.py"


def run_cleanup(args: list[str], *, sejong_home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEJONG_HOME"] = str(sejong_home)
    return subprocess.run(
        [sys.executable, str(CLEANUP), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def make_run(sejong_home: Path, repo_id: str = "repo-test", run_id: str = "run-test") -> Path:
    run_dir = sejong_home / "runs" / repo_id / run_id
    run_dir.mkdir(parents=True)
    return run_dir


def write_active_context(sejong_home: Path, *, repo_id: str, run_id: str) -> None:
    state_dir = sejong_home / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "active-context.json").write_text(
        json.dumps(
            {
                "format": "king-sejong.context/v0.1-draft",
                "active_context_id": "ctx-test",
                "repo_id": repo_id,
                "repo_root": "/tmp/repo-test",
                "run_id": run_id,
                "session_id": "session-test",
                "route_id": "route-test",
                "current_surface": "seungjeongwon",
                "route_sequence": ["uigwe", "seungjeongwon"],
                "required_route_sequence": ["uigwe", "seungjeongwon"],
                "last_user_intent": "test",
                "pending_gates": [],
                "protected_paths": [],
                "allowed_direct_change_types": [],
                "evidence_refs": [],
                "artifact_refs": [],
                "team_run_refs": [],
                "subagent_refs": [],
                "exit_conditions": ["test"],
                "last_updated_at": "2026-06-20T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )


class SejongCleanupTests(unittest.TestCase):
    def test_finalize_success_dry_run_keeps_raw_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "sillok-record.jsonl").write_text("", encoding="utf-8")
            (run_dir / "plan.packet.json").write_text("{}", encoding="utf-8")

            result = run_cleanup(["finalize-run", str(run_dir), "--status", "success"], sejong_home=sejong_home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((run_dir / "plan.packet.json").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertIn("plan.packet.json", summary["actions"]["would_delete"])
            self.assertTrue(summary["dry_run"])

    def test_finalize_success_execute_deletes_raw_and_keeps_compact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "sillok-record.jsonl").write_text("", encoding="utf-8")
            (run_dir / "execution-ledger.jsonl").write_text("", encoding="utf-8")

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((run_dir / "sillok-record.jsonl").exists())
            self.assertTrue((run_dir / "run-summary.json").exists())
            self.assertFalse((run_dir / "execution-ledger.jsonl").exists())

    def test_finalize_execute_refuses_active_run_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home, repo_id="repo-test", run_id="active-run")
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")
            write_active_context(sejong_home, repo_id="repo-test", run_id="active-run")

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((run_dir / "scratch.log").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertIn("active run is protected from cleanup", summary["actions"]["failures"])

    def test_promoted_marker_protects_raw_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / ".sejong-promoted").write_text("", encoding="utf-8")
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((run_dir / "scratch.log").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertIn("promoted run is protected from cleanup", summary["actions"]["failures"])

    def test_prune_runs_refuses_paths_outside_sejong_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp) / "sejong"
            outside = Path(tmp) / "outside"
            outside.mkdir()

            result = run_cleanup(["prune-runs", str(outside)], sejong_home=sejong_home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside Sejong runs root", result.stderr)


if __name__ == "__main__":
    unittest.main()
