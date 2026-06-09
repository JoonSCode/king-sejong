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


class TaskClassDelegationGateTests(unittest.TestCase):
    def test_simple_low_overhead_task_uses_direct_execution(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="install_maintenance",
                write_risk="low",
                evidence_breadth="narrow",
                code_coupling="isolated",
                overhead_roi="low",
            )
        )

        self.assertEqual(result["selected_route"], "direct_execution")
        self.assertEqual(result["hard_gate_failures"], [])
        self.assertIn("implementation notes", result["allowed_outputs"])

    def test_broad_disjoint_high_roi_execution_uses_team_executor(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="implementation",
                write_risk="medium",
                evidence_breadth="broad",
                code_coupling="bounded",
                overhead_roi="high",
                worker_scope_state="disjoint",
                uigwe_contract_state="handoff_ready",
            )
        )

        self.assertEqual(result["selected_route"], "team_executor")
        self.assertIn("durable mailbox or workflow-run evidence", result["required_evidence"])
        self.assertIn("Uigwe contract refs preserved", result["required_evidence"])
        self.assertIn("majority-vote authority", result["forbidden_claims"])

    def test_moderate_independent_work_uses_bounded_subagents(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="validation_review",
                write_risk="low",
                evidence_breadth="moderate",
                code_coupling="isolated",
                overhead_roi="medium",
                worker_scope_state="disjoint",
            )
        )

        self.assertEqual(result["selected_route"], "bounded_subagents")
        self.assertIn("bounded worker scope", result["required_evidence"])

    def test_research_task_uses_research_fanout(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="research",
                write_risk="none",
                evidence_breadth="unknown",
                code_coupling="cross_module",
                overhead_roi="medium",
            )
        )

        self.assertEqual(result["selected_route"], "research_fanout")
        self.assertEqual(result["hard_gate_failures"], [])
        self.assertEqual(result["recommended_reentry_target"], "jangyeongsil")
        self.assertIn("known/inferred/unknown separation", result["required_evidence"])

    def test_hard_gate_violation_forces_no_write_dry_run(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="implementation",
                write_risk="medium",
                evidence_breadth="broad",
                code_coupling="bounded",
                overhead_roi="high",
                worker_scope_state="disjoint",
                worker_authority_policy="consensus_approval",
            )
        )

        self.assertEqual(result["selected_route"], "no_write_dry_run")
        self.assertIn("keeps_worker_outputs_evidence_only", result["hard_gate_failures"])
        self.assertFalse(result["hard_gates"]["keeps_worker_outputs_evidence_only"])
        self.assertEqual(result["recommended_reentry_target"], "none")

    def test_missing_uigwe_contract_for_writes_forces_uigwe_reentry(self) -> None:
        result = gate.evaluate(
            gate.DelegationInput(
                task_class="bundle_execution",
                write_risk="medium",
                evidence_breadth="moderate",
                code_coupling="bounded",
                overhead_roi="medium",
                uigwe_contract_state="required_missing",
            )
        )

        self.assertEqual(result["selected_route"], "no_write_dry_run")
        self.assertIn("uigwe_contract_required_before_writes", result["hard_gate_failures"])
        self.assertEqual(result["recommended_reentry_target"], "uigwe")

    def test_cli_reads_json_and_emits_stable_format(self) -> None:
        payload = {
            "task_class": "implementation",
            "write_risk": "medium",
            "evidence_breadth": "broad",
            "code_coupling": "bounded",
            "overhead_roi": "high",
            "worker_scope_state": "disjoint",
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "task.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--from-json", str(input_path)],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["format"], gate.FORMAT)
        self.assertEqual(report["selected_route"], "team_executor")


if __name__ == "__main__":
    unittest.main()
