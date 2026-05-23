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
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"


def run_context(args: list[str], *, sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


class SejongContextTests(unittest.TestCase):
    def test_start_update_doctor_and_close_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "ctx-test",
                    "--current-surface",
                    "jiphyeonjeon",
                    "--required-route",
                    "jiphyeonjeon",
                    "--required-route",
                    "uigwe",
                    "--required-route",
                    "seungjeongwon",
                    "--protected-path",
                    "docs/sejong/",
                    "--last-user-intent",
                    "test active context",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            active_path = sejong_home / "state" / "active-context.json"
            self.assertTrue(active_path.exists())

            context = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(context["current_surface"], "jiphyeonjeon")
            self.assertIn("docs/sejong/", context["protected_paths"])
            run_context_path = sejong_home / "runs" / context["repo_id"] / "ctx-test" / "king-sejong-context.json"
            self.assertTrue(run_context_path.exists())

            update = run_context(
                [
                    "update",
                    "--current-surface",
                    "seungjeongwon",
                    "--append-route",
                    "uigwe",
                    "--append-route",
                    "seungjeongwon",
                    "--add-pending-gate",
                    "verification",
                    "--add-evidence-ref",
                    "evidence.json",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(update.returncode, 0, update.stderr)

            updated = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["current_surface"], "seungjeongwon")
            self.assertEqual(updated["route_sequence"], ["jiphyeonjeon", "uigwe", "seungjeongwon"])
            self.assertEqual(updated["pending_gates"], ["verification"])
            self.assertEqual(updated["evidence_refs"], ["evidence.json"])

            doctor = run_context(["doctor", "--repo-root", str(REPO_ROOT)], sejong_home=sejong_home)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertIn("context ok", doctor.stdout)

            close = run_context(["close"], sejong_home=sejong_home)
            self.assertEqual(close.returncode, 0, close.stderr)
            self.assertFalse(active_path.exists())
            self.assertTrue(run_context_path.exists())


if __name__ == "__main__":
    unittest.main()
