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
            self.assertEqual(updated["pending_gates"], ["seungjeongwon_receipt_required", "verification"])
            self.assertEqual(updated["evidence_refs"], ["evidence.json"])

            doctor = run_context(["doctor", "--repo-root", str(REPO_ROOT)], sejong_home=sejong_home)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertIn("context ok", doctor.stdout)

            close = run_context(["close"], sejong_home=sejong_home)
            self.assertEqual(close.returncode, 0, close.stderr)
            self.assertFalse(active_path.exists())
            self.assertTrue(run_context_path.exists())

    def test_start_goal_bearing_adds_receipt_gate_and_required_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "goal-bearing",
                    "--goal-bearing",
                    "--last-user-intent",
                    "implement app-quality workflow",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            context = json.loads((sejong_home / "state" / "active-context.json").read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_update_can_require_seungjeongwon_receipt_without_manual_gate_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "receipt-update",
                    "--last-user-intent",
                    "continue app workflow",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            update = run_context(["update", "--require-seungjeongwon-receipt"], sejong_home=sejong_home)
            self.assertEqual(update.returncode, 0, update.stderr)

            context = json.loads((sejong_home / "state" / "active-context.json").read_text(encoding="utf-8"))
            self.assertIn("seungjeongwon", context["required_route_sequence"])
            self.assertIn("seungjeongwon_receipt_required", context["pending_gates"])

    def test_doctor_reports_repair_command_for_invalid_list_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_path = sejong_home / "state" / "active-context.json"
            active_path.parent.mkdir(parents=True)
            active_path.write_text(
                json.dumps(
                    {
                        "format": "king-sejong.context/v0.1-draft",
                        "active_context_id": "ctx-invalid",
                        "repo_id": "repo",
                        "repo_root": str(REPO_ROOT),
                        "run_id": "run-invalid",
                        "session_id": "session-invalid",
                        "route_id": "route-invalid",
                        "current_surface": "sejong",
                        "route_sequence": ["sejong"],
                        "required_route_sequence": [],
                        "last_user_intent": "invalid context fixture",
                        "pending_gates": [],
                        "protected_paths": [],
                        "allowed_direct_change_types": [],
                        "evidence_refs": [{"ref": "user-approved-plugin-adapter-direction"}],
                        "artifact_refs": [],
                        "team_run_refs": [],
                        "subagent_refs": [],
                        "exit_conditions": ["host_conversation_ends"],
                        "last_updated_at": "2026-06-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            doctor = run_context(["doctor", "--repo-root", str(REPO_ROOT)], sejong_home=sejong_home)
            self.assertNotEqual(doctor.returncode, 0)
            self.assertIn("evidence_refs must contain only non-empty strings", doctor.stderr)
            self.assertIn("repair suggestion:", doctor.stderr)
            self.assertIn("sejong_context.py repair", doctor.stderr)

    def test_repair_coerces_invalid_list_item_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_path = sejong_home / "state" / "active-context.json"
            active_path.parent.mkdir(parents=True)
            active_path.write_text(
                json.dumps(
                    {
                        "format": "king-sejong.context/v0.1-draft",
                        "active_context_id": "ctx-invalid",
                        "repo_id": "repo",
                        "repo_root": str(REPO_ROOT),
                        "run_id": "run-invalid",
                        "session_id": "session-invalid",
                        "route_id": "route-invalid",
                        "current_surface": "sejong",
                        "route_sequence": ["sejong"],
                        "required_route_sequence": [],
                        "last_user_intent": "invalid context fixture",
                        "pending_gates": [],
                        "protected_paths": [],
                        "allowed_direct_change_types": [],
                        "evidence_refs": [{"ref": "user-approved-plugin-adapter-direction"}],
                        "artifact_refs": [],
                        "team_run_refs": [],
                        "subagent_refs": [],
                        "exit_conditions": ["host_conversation_ends"],
                        "last_updated_at": "2026-06-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            repair = run_context(["repair"], sejong_home=sejong_home)
            self.assertEqual(repair.returncode, 0, repair.stderr)
            repaired = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["evidence_refs"], ["user-approved-plugin-adapter-direction"])

            doctor = run_context(["doctor", "--repo-root", str(REPO_ROOT)], sejong_home=sejong_home)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)


if __name__ == "__main__":
    unittest.main()
