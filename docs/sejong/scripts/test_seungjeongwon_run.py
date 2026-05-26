#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "seungjeongwon_run.py"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class SeungjeongwonRunTests(unittest.TestCase):
    def test_run_lifecycle_requires_attempts_before_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "seungjeongwon-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "run-tagback",
                    "--repo-root",
                    ".",
                    "--goal",
                    "Improve TagBack growth strategy quality.",
                    "--success-criterion",
                    "Candidate score beats baseline by at least 0.12.",
                    "--verification-method",
                    "Run outcome_quality_evaluator compare.",
                    "--todo",
                    "T1|Score current latest SOT baseline|Baseline score is recorded|outcome evaluator",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            premature = run_command(["complete", "--path", str(run_path), "--verification-evidence", "not enough"])
            self.assertNotEqual(premature.returncode, 0)
            self.assertIn("open todos remain", premature.stderr)

            attempt = run_command(
                [
                    "record-attempt",
                    "--path",
                    str(run_path),
                    "--todo-id",
                    "T1",
                    "--hypothesis",
                    "Structured runtime contracts improve actionability.",
                    "--action",
                    "Compared baseline and candidate artifacts.",
                    "--verification",
                    "score_delta >= 0.12",
                    "--result",
                    "pass",
                    "--finding",
                    "Candidate cleared threshold.",
                    "--next-decision",
                    "complete todo",
                ]
            )
            self.assertEqual(attempt.returncode, 0, attempt.stderr)

            todo = run_command(["complete-todo", "--path", str(run_path), "--todo-id", "T1"])
            self.assertEqual(todo.returncode, 0, todo.stderr)

            complete = run_command(["complete", "--path", str(run_path), "--verification-evidence", "score_delta=0.28"])
            self.assertEqual(complete.returncode, 0, complete.stderr)

            check = run_command(["check", "--path", str(run_path)])
            self.assertEqual(check.returncode, 0, check.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "sejong.seungjeongwon-run/v0.1-draft")
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["todos"][0]["status"], "completed")

    def test_check_rejects_completed_run_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "bad-run.json"
            run_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.seungjeongwon-run/v0.1-draft",
                        "run_id": "bad",
                        "repo_root": ".",
                        "goal": "Goal",
                        "status": "completed",
                        "success_criteria": ["Done"],
                        "verification_methods": ["Test"],
                        "todos": [],
                        "attempt_ledger": [],
                        "verification_evidence": [],
                        "blockers": [],
                        "uigwe_reentry_requests": [],
                        "created_at": "2026-05-26T00:00:00Z",
                        "updated_at": "2026-05-26T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            result = run_command(["check", "--path", str(run_path)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completed run requires verification evidence", result.stderr)


if __name__ == "__main__":
    unittest.main()
