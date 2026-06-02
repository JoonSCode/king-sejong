#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "continuity_capsule.py"
EXAMPLE = SEJONG_ROOT / "examples" / "continuity-capsule.example.json"


def run_capsule(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class ContinuityCapsuleTests(unittest.TestCase):
    def test_example_capsule_validates(self) -> None:
        result = run_capsule(["check", "--path", str(EXAMPLE)])
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("continuity capsule ok", result.stdout)

    def test_standard_projection_is_compact_and_decision_bearing(self) -> None:
        result = run_capsule(["project", "--path", str(EXAMPLE), "--profile", "standard"])
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("continuity_capsule=capsule-continuity-example", result.stdout)
        self.assertIn("profile=standard", result.stdout)
        self.assertIn("continuity_decision=Use a continuity capsule", result.stdout)
        self.assertNotIn("Replay full trace history", result.stdout)

    def test_start_creates_minimal_valid_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "continuity-capsule.json"
            result = run_capsule(
                [
                    "start",
                    "--path",
                    str(path),
                    "--capsule-id",
                    "capsule-test",
                    "--active-context-id",
                    "ctx-test",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run-test",
                    "--objective",
                    "Preserve compact continuity.",
                    "--task-class",
                    "runtime-contract-design",
                    "--current-surface",
                    "uigwe",
                    "--next-action",
                    "Continue with hook wiring.",
                    "--source-artifact-ref",
                    "king-sejong-context.json",
                    "--verification-ref",
                    "docs/sejong/scripts/test_continuity_capsule.py",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            check = run_capsule(["check", "--path", str(path)])
            self.assertEqual(check.returncode, 0, check.stderr or check.stdout)

    def test_update_moves_runtime_fields_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "continuity-capsule.json"
            start = run_capsule(
                [
                    "start",
                    "--path",
                    str(path),
                    "--capsule-id",
                    "capsule-update",
                    "--active-context-id",
                    "ctx-update",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run-update",
                    "--objective",
                    "Preserve compact continuity.",
                    "--task-class",
                    "runtime-contract-design",
                    "--current-surface",
                    "uigwe",
                    "--next-action",
                    "Create capsule.",
                    "--source-artifact-ref",
                    "king-sejong-context.json",
                    "--verification-ref",
                    "initial-check",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr or start.stdout)

            update = run_capsule(
                [
                    "update",
                    "--path",
                    str(path),
                    "--current-surface",
                    "seungjeongwon",
                    "--route",
                    "seungjeongwon",
                    "--clear-active-blockers",
                    "--active-blocker",
                    "verification pending",
                    "--pending-gate",
                    "seungjeongwon_receipt_required",
                    "--next-action",
                    "Run hook tests.",
                    "--verification-status",
                    "in_progress",
                    "--last-verified-claim",
                    "Hook tests are queued.",
                    "--verification-ref",
                    "docs/sejong/scripts/test_king_sejong_hooks.py",
                ]
            )
            self.assertEqual(update.returncode, 0, update.stderr or update.stdout)
            projection = run_capsule(["project", "--path", str(path), "--profile", "standard"])
            self.assertIn("surface=seungjeongwon", projection.stdout)
            self.assertIn("next_action=Run hook tests.", projection.stdout)
            self.assertIn("blockers=verification pending", projection.stdout)

    def test_records_decisions_and_rejections_without_manual_json_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "continuity-capsule.json"
            start = run_capsule(
                [
                    "start",
                    "--path",
                    str(path),
                    "--capsule-id",
                    "capsule-decision",
                    "--active-context-id",
                    "ctx-decision",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run-decision",
                    "--objective",
                    "Preserve compact continuity.",
                    "--task-class",
                    "runtime-contract-design",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--projection-profile",
                    "frontier",
                    "--next-action",
                    "Record decision.",
                    "--source-artifact-ref",
                    "king-sejong-context.json",
                    "--verification-ref",
                    "initial-check",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr or start.stdout)

            decision = run_capsule(
                [
                    "record-decision",
                    "--path",
                    str(path),
                    "--decision-id",
                    "capsule-as-index",
                    "--summary",
                    "Use capsule as compact artifact index.",
                    "--why",
                    "It preserves working state without raw replay.",
                    "--ref",
                    "docs/sejong/CONTINUITY.md",
                ]
            )
            self.assertEqual(decision.returncode, 0, decision.stderr or decision.stdout)
            rejection = run_capsule(
                [
                    "record-rejection",
                    "--path",
                    str(path),
                    "--option-id",
                    "handoff-only",
                    "--summary",
                    "Use only markdown handoff.",
                    "--reason",
                    "It is not hook-validated AI working state.",
                    "--ref",
                    "docs/sejong/ROUTER.md",
                ]
            )
            self.assertEqual(rejection.returncode, 0, rejection.stderr or rejection.stdout)
            projection = run_capsule(["project", "--path", str(path), "--profile", "frontier"])
            self.assertIn("continuity_decision=Use capsule as compact artifact index.", projection.stdout)
            self.assertIn("continuity_rejected=Use only markdown handoff.", projection.stdout)


if __name__ == "__main__":
    unittest.main()
