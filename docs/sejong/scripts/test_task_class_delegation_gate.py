#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "task_class_delegation_gate.py"
sys.path.insert(0, str(SEJONG_ROOT / "scripts"))

import task_class_delegation_gate as gate  # noqa: E402


def broad_input() -> gate.DelegationInput:
    return gate.DelegationInput(
        task_class="implementation",
        write_risk="medium",
        evidence_breadth="broad",
        code_coupling="bounded",
        overhead_roi="high",
        worker_scope_state="disjoint",
        team_executor_health="healthy",
    )


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
        result = gate.evaluate(replace(
            broad_input(), uigwe_contract_state="handoff_ready",
        ))

        self.assertEqual(result["selected_route"], "team_executor")
        self.assertIn(
            "durable mailbox or workflow-run evidence", result["required_evidence"]
        )
        self.assertIn("Uigwe contract refs preserved", result["required_evidence"])
        self.assertIn("majority-vote authority", result["forbidden_claims"])
        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertEqual(result["fallback_reasons"], [])
        self.assertIn("host_native_capability_unknown", result["capability_notes"])

    def test_native_available_prefers_bounded_subagents_for_broad_execution(
        self,
    ) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            uigwe_contract_state="handoff_ready",
            host_native_state="available",
        ))

        self.assertEqual(result["selected_route"], "bounded_subagents")
        self.assertEqual(result["selected_backend"], "codex_native")
        self.assertEqual(result["fallback_reasons"], [])
        self.assertIn("native agent thread refs", result["required_evidence"])

    def test_native_unavailable_uses_team_executor_fallback(self) -> None:
        result = gate.evaluate(replace(
            broad_input(), host_native_state="unavailable",
        ))

        self.assertEqual(result["selected_route"], "team_executor")
        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("host_native_unavailable", result["fallback_reasons"])

    def test_undetected_team_executor_falls_back_for_optional_work(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            host_native_state="unavailable",
            team_executor_health="undetected",
        ))

        self.assertEqual(result["selected_route"], "direct_execution")
        self.assertEqual(result["selected_backend"], "current_session")
        self.assertEqual(result["backend_health"]["team_executor"], "undetected")
        self.assertIn("team_executor_health_undetected", result["capability_notes"])

    def test_unhealthy_team_executor_blocks_required_worker_capability(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            host_native_state="unavailable",
            team_executor_health="unhealthy",
            requires_independent_process=True,
        ))

        self.assertEqual(result["selected_route"], "no_write_dry_run")
        self.assertEqual(result["selected_backend"], "none")
        self.assertEqual(result["recommended_reentry_target"], "seungjeongwon")
        self.assertIn("team_executor_health_unhealthy", result["capability_notes"])

    def test_independent_process_requirement_uses_team_executor(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            host_native_state="available",
            requires_independent_process=True,
        ))

        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("independent_process_required", result["fallback_reasons"])

    def test_explicit_process_requirement_overrides_unknown_native_capability(
        self,
    ) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            task_class="validation_review",
            write_risk="low",
            evidence_breadth="moderate",
            code_coupling="isolated",
            overhead_roi="medium",
            requires_independent_process=True,
        ))

        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("independent_process_required", result["fallback_reasons"])

    def test_cross_session_recovery_requirement_uses_team_executor(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            task_class="bundle_execution",
            host_native_state="available",
            requires_cross_session_recovery=True,
        ))

        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("cross_session_recovery_required", result["fallback_reasons"])

    def test_shared_workspace_native_host_cannot_satisfy_write_isolation(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            host_native_state="available",
            host_native_write_isolation="shared_workspace",
            requires_write_isolation=True,
        ))

        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("native_write_isolation_unavailable", result["fallback_reasons"])

    def test_native_worktree_isolation_satisfies_write_isolation_requirement(
        self,
    ) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            host_native_state="available",
            host_native_write_isolation="worktree",
            requires_write_isolation=True,
        ))

        self.assertEqual(result["selected_route"], "bounded_subagents")
        self.assertEqual(result["selected_backend"], "codex_native")
        self.assertEqual(result["fallback_reasons"], [])

    def test_missing_native_peer_messaging_uses_team_executor(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            task_class="validation_review",
            write_risk="low",
            host_native_state="available",
            host_native_direct_messaging="unavailable",
            requires_peer_messaging=True,
        ))

        self.assertEqual(result["selected_backend"], "team_executor")
        self.assertIn("native_peer_messaging_unavailable", result["fallback_reasons"])

    def test_available_native_peer_messaging_keeps_native_backend(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            task_class="validation_review",
            write_risk="low",
            host_native_state="available",
            host_native_direct_messaging="available",
            requires_peer_messaging=True,
        ))

        self.assertEqual(result["selected_backend"], "codex_native")
        self.assertEqual(result["fallback_reasons"], [])

    def test_moderate_independent_work_uses_bounded_subagents(self) -> None:
        result = gate.evaluate(replace(
            broad_input(),
            task_class="validation_review",
            write_risk="low",
            evidence_breadth="moderate",
            code_coupling="isolated",
            overhead_roi="medium",
        ))

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
        result = gate.evaluate(replace(
            broad_input(),
            worker_authority_policy="consensus_approval",
        ))

        self.assertEqual(result["selected_route"], "no_write_dry_run")
        self.assertIn(
            "keeps_worker_outputs_evidence_only", result["hard_gate_failures"]
        )
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
        self.assertIn(
            "uigwe_contract_required_before_writes", result["hard_gate_failures"]
        )
        self.assertEqual(result["recommended_reentry_target"], "uigwe")

    def test_cli_reads_json_and_emits_stable_format(self) -> None:
        payload = {
            "task_class": "implementation",
            "write_risk": "medium",
            "evidence_breadth": "broad",
            "code_coupling": "bounded",
            "overhead_roi": "high",
            "worker_scope_state": "disjoint",
            "team_executor_health": "healthy",
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
        self.assertEqual(report["selected_backend"], "team_executor")

    def test_cli_auto_fingerprint_excludes_undetected_team_executor(self) -> None:
        payload = {
            "task_class": "implementation",
            "write_risk": "medium",
            "evidence_breadth": "broad",
            "code_coupling": "bounded",
            "overhead_roi": "high",
            "worker_scope_state": "disjoint",
            "host_native_state": "unavailable",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "task.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            missing_bin = root / "missing-bin"
            missing_bin.mkdir()
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--from-json", str(input_path)],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PATH": str(missing_bin)},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["selected_route"], "direct_execution")
        self.assertEqual(report["backend_health"]["team_executor"], "undetected")

if __name__ == "__main__":
    unittest.main()
