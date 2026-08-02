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
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"


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


def run_context(args: list[str], *, sejong_home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEJONG_HOME"] = str(sejong_home)
    env["SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS"] = "1.0"
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def make_run(sejong_home: Path, repo_id: str = "repo-test", run_id: str = "run-test") -> Path:
    run_dir = sejong_home / "runs" / repo_id / run_id
    run_dir.mkdir(parents=True)
    return run_dir


def write_active_context(
    sejong_home: Path,
    *,
    repo_id: str,
    run_id: str,
    artifact_refs: list[str] | None = None,
) -> None:
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
                "artifact_refs": artifact_refs or [],
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

    def test_finalize_success_execute_preserves_non_authoritative_legacy_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home, repo_id="repo-test", run_id="active-run")
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")
            write_active_context(sejong_home, repo_id="repo-test", run_id="active-run")

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((run_dir / "scratch.log").exists())
            self.assertTrue((sejong_home / "state" / "active-context.json").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["actions"]["closed_active_context"])

    def test_finalize_execute_ignores_non_authoritative_legacy_artifact_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home, repo_id="repo-test", run_id="referenced-run")
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")
            write_active_context(
                sejong_home,
                repo_id="repo-test",
                run_id="other-active-run",
                artifact_refs=[str(run_dir / "king-sejong-context.json")],
            )

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((run_dir / "scratch.log").exists())
            self.assertTrue((sejong_home / "state" / "active-context.json").exists())
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["actions"]["failures"], [])

    def test_finalize_execute_refuses_exactly_bound_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            started = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--repo-id",
                    "repo-test",
                    "--run-id",
                    "bound-run",
                    "--session-id",
                    "session-bound",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_dir = sejong_home / "runs" / "repo-test" / "bound-run"
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")

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

    def test_prune_runs_uses_session_binding_protection_without_legacy_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "run-summary.json").write_text(
                json.dumps({"status": "success"}),
                encoding="utf-8",
            )

            result = run_cleanup(["prune-runs"], sejong_home=sejong_home)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["format"], "sejong.cleanup-report/v0.1-draft")
            self.assertEqual(len(report["results"]), 1)

    def test_report_uses_session_binding_protection_without_legacy_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")

            result = run_cleanup(["report"], sejong_home=sejong_home)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["format"], "sejong.cleanup-inventory/v0.1-draft")
            self.assertEqual(report["run_count"], 1)
            self.assertFalse(report["runs"][0]["active"])

    def test_finalize_reports_lifecycle_counts_and_missing_cleanup_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "work-events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"format": "sejong.work-event/v0.1-draft", "run_id": "run-test"}),
                        json.dumps({"format": "sejong.work-event/v0.1-draft", "run_id": "run-other"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "lesson-candidate.json").write_text(
                json.dumps({"format": "sejong.lesson-candidate/v0.1-draft", "candidate_id": "candidate-test"}),
                encoding="utf-8",
            )
            (run_dir / "worker-resource-lease.json").write_text(
                json.dumps(
                    {
                        "format": "sejong.worker-resource-lease/v0.1-draft",
                        "lease_id": "lease-test",
                        "status": "released",
                    }
                ),
                encoding="utf-8",
            )

            result = run_cleanup(["finalize-run", str(run_dir), "--status", "success"], sejong_home=sejong_home)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["lifecycle"]["event_count"], 2)
            self.assertEqual(summary["lifecycle"]["lesson_candidate_count"], 1)
            self.assertEqual(summary["lifecycle"]["cleanup_evidence"]["lease_count"], 1)
            self.assertEqual(summary["lifecycle"]["cleanup_evidence"]["receipt_count"], 0)
            self.assertFalse(summary["lifecycle"]["cleanup_evidence"]["proof_complete"])
            self.assertEqual(summary["lifecycle"]["cleanup_evidence"]["gaps"], ["lease-test"])

    def test_finalize_rejects_malformed_lifecycle_artifact_without_deleting_raw_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_dir = make_run(sejong_home)
            (run_dir / "work-events.jsonl").write_text("{not-json}\n", encoding="utf-8")
            (run_dir / "scratch.log").write_text("raw", encoding="utf-8")

            result = run_cleanup(
                ["finalize-run", str(run_dir), "--status", "success", "--execute"],
                sejong_home=sejong_home,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid lifecycle artifact", result.stderr)
            self.assertTrue((run_dir / "scratch.log").exists())


if __name__ == "__main__":
    unittest.main()
