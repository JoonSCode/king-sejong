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
RUNNER = SEJONG_ROOT / "scripts" / "task_class_delegation_gate.py"
sys.path.insert(0, str(SEJONG_ROOT / "scripts"))

import task_class_delegation_gate as gate  # noqa: E402


class TaskClassDelegationBoundaryTests(unittest.TestCase):
    def test_explicit_backend_requirements_override_simple_direct_scores(self) -> None:
        cases = (
            gate.DelegationInput(
                task_class="simple_lookup", requires_independent_process=True,
            ),
            gate.DelegationInput(
                task_class="simple_lookup", requires_cross_session_recovery=True,
            ),
            gate.DelegationInput(
                task_class="simple_lookup", requires_write_isolation=True,
            ),
            gate.DelegationInput(
                task_class="simple_lookup", requires_peer_messaging=True,
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                result = gate.evaluate(case)

            self.assertEqual(result["selected_route"], "team_executor")
            self.assertEqual(result["selected_backend"], "team_executor")

    def test_satisfied_native_requirements_override_simple_direct_scores(self) -> None:
        cases = (
            gate.DelegationInput(
                task_class="simple_lookup",
                host_native_state="available",
                host_native_write_isolation="worktree",
                requires_write_isolation=True,
            ),
            gate.DelegationInput(
                task_class="simple_lookup",
                host_native_state="available",
                host_native_direct_messaging="available",
                requires_peer_messaging=True,
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                result = gate.evaluate(case)

            self.assertEqual(result["selected_route"], "bounded_subagents")
            self.assertEqual(result["selected_backend"], "codex_native")

    def test_unsafe_scope_blocks_required_backend(self) -> None:
        cases = (
            gate.DelegationInput(
                task_class="simple_lookup",
                host_native_state="unavailable",
                worker_scope_state="overlapping",
                requires_independent_process=True,
            ),
            gate.DelegationInput(
                task_class="simple_lookup",
                host_native_state="unavailable",
                worker_scope_state="unknown",
                requires_independent_process=True,
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                result = gate.evaluate(case)

            self.assertEqual(result["selected_route"], "no_write_dry_run")
            self.assertIn("worker_scope_unsafe", result["hard_gate_failures"])

    def test_json_requires_flags_reject_non_boolean_values(self) -> None:
        invalid = {
            "requires_independent_process": 0,
            "requires_cross_session_recovery": "false",
            "requires_write_isolation": [],
            "requires_peer_messaging": {},
        }
        for field, value in invalid.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                input_path = Path(tmp) / "task.json"
                input_path.write_text(json.dumps({
                    "task_class": "implementation", field: value,
                }), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(RUNNER), "--from-json", str(input_path)],
                    text=True,
                    capture_output=True,
                    cwd=str(REPO_ROOT),
                )

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(f"{field} must be a boolean", result.stderr)


if __name__ == "__main__":
    unittest.main()
