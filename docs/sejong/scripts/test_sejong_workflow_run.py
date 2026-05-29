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
RUNNER = SEJONG_ROOT / "scripts" / "sejong_workflow_run.py"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class SejongWorkflowRunTests(unittest.TestCase):
    def test_shadow_run_lifecycle_records_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "deep-research-shadow",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "deep_research",
                    "--workflow-name",
                    "jangyeongsil-claim-cross-check-shadow",
                    "--backend",
                    "manual_shadow",
                    "--mapped-surface",
                    "jangyeongsil",
                    "--mapped-surface",
                    "sillok",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Discarded and supported claims are separated before Sejong synthesis.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)

            worker = run_command(
                [
                    "add-worker",
                    "--path",
                    str(run_path),
                    "--worker-id",
                    "research-lane-1",
                    "--role",
                    "bounded research",
                    "--scope",
                    "Cross-check dynamic workflow claims against source refs.",
                    "--allowed-output",
                    "known/inferred/unknown evidence only",
                    "--write-scope",
                    "workflow-run.evidence_ledger",
                ]
            )
            self.assertEqual(worker.returncode, 0, worker.stderr)

            source = run_command(
                [
                    "add-evidence",
                    "--path",
                    str(run_path),
                    "--evidence-id",
                    "source-1",
                    "--kind",
                    "source_ref",
                    "--summary",
                    "Source-of-truth documents were checked.",
                    "--ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--status",
                    "supported",
                ]
            )
            self.assertEqual(source.returncode, 0, source.stderr)

            cross_check = run_command(
                [
                    "add-evidence",
                    "--path",
                    str(run_path),
                    "--evidence-id",
                    "cross-check-1",
                    "--kind",
                    "cross_check",
                    "--summary",
                    "Claims were cross-checked before synthesis.",
                    "--ref",
                    "docs/sejong/VALIDATION.md",
                    "--status",
                    "verified",
                ]
            )
            self.assertEqual(cross_check.returncode, 0, cross_check.stderr)

            evidence = run_command(
                [
                    "add-evidence",
                    "--path",
                    str(run_path),
                    "--evidence-id",
                    "discarded-claim-1",
                    "--kind",
                    "discarded_claim",
                    "--summary",
                    "Worker majority does not approve Uigwe gates.",
                    "--ref",
                    "docs/sejong/TEAM_EXECUTOR.md",
                    "--status",
                    "rejected",
                ]
            )
            self.assertEqual(evidence.returncode, 0, evidence.stderr)

            verification = run_command(
                [
                    "add-evidence",
                    "--path",
                    str(run_path),
                    "--evidence-id",
                    "verification-1",
                    "--kind",
                    "verification_ref",
                    "--summary",
                    "Workflow-run check command passed.",
                    "--ref",
                    "python3 docs/sejong/scripts/sejong_workflow_run.py check",
                    "--status",
                    "verified",
                ]
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)

            comparison = run_command(
                [
                    "record-comparison",
                    "--path",
                    str(run_path),
                    "--baseline-result-ref",
                    "baseline:single-agent-research",
                    "--candidate-result-ref",
                    "candidate:shadow-workflow-ledger",
                    "--acceptance-criterion",
                    "Candidate improves claim separation without authority drift.",
                    "--outcome-quality-delta",
                    "0.05",
                    "--overhead-ratio",
                    "1.2",
                    "--recommendation",
                    "keep_shadowing",
                ]
            )
            self.assertEqual(comparison.returncode, 0, comparison.stderr)

            complete = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "python3 docs/sejong/scripts/sejong_workflow_run.py check --path workflow-run.json",
                    "--final-recommendation",
                    "keep_shadowing",
                ]
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)

            check = run_command(["check", "--path", str(run_path)])
            self.assertEqual(check.returncode, 0, check.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "sejong.workflow-run/v0.1-draft")
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["quality_comparison"]["recommendation"], "keep_shadowing")
            self.assertEqual(data["final_recommendation"], "keep_shadowing")

    def test_promote_requires_positive_quality_delta_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "bad-promote",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "bad-promotion",
                    "--backend",
                    "manual_shadow",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Promotion beats baseline.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            comparison = run_command(
                [
                    "record-comparison",
                    "--path",
                    str(run_path),
                    "--baseline-result-ref",
                    "baseline:bad-promote",
                    "--candidate-result-ref",
                    "candidate:bad-promote",
                    "--acceptance-criterion",
                    "Positive quality delta.",
                    "--outcome-quality-delta",
                    "0.0",
                    "--overhead-ratio",
                    "1.0",
                    "--recommendation",
                    "promote",
                ]
            )
            self.assertEqual(comparison.returncode, 0, comparison.stderr)
            promote = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "shadow comparison complete",
                    "--final-recommendation",
                    "promote",
                ]
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("promote requires positive outcome_quality_delta", promote.stderr)

    def test_promote_requires_minimum_quality_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "weak-promote",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "weak-promotion",
                    "--backend",
                    "codex_mock_workflow",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Promotion beats baseline by the minimum quality threshold.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            comparison = run_command(
                [
                    "record-comparison",
                    "--path",
                    str(run_path),
                    "--baseline-result-ref",
                    "baseline:weak-promote",
                    "--candidate-result-ref",
                    "candidate:weak-promote",
                    "--acceptance-criterion",
                    "Candidate beats the same task rubric by a meaningful margin.",
                    "--outcome-quality-delta",
                    "0.01",
                    "--overhead-ratio",
                    "1.0",
                    "--recommendation",
                    "promote",
                ]
            )
            self.assertEqual(comparison.returncode, 0, comparison.stderr)
            promote = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "shadow comparison complete",
                    "--final-recommendation",
                    "promote",
                ]
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("promote requires outcome_quality_delta >= 0.10", promote.stderr)

    def test_completed_run_rejects_empty_acceptance_criteria_and_mismatched_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "bad-comparison",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "bad-comparison",
                    "--backend",
                    "codex_mock_workflow",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Comparison must be reviewable.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            data = json.loads(run_path.read_text(encoding="utf-8"))
            data["quality_comparison"] = {
                "baseline_result_ref": "baseline:bad-comparison",
                "candidate_result_ref": "candidate:bad-comparison",
                "acceptance_criteria": [],
                "outcome_quality_delta": 0.2,
                "overhead_ratio": 1.0,
                "recommendation": "promote",
            }
            data["evidence_ledger"].append(
                {
                    "evidence_id": "verification-1",
                    "kind": "verification_ref",
                    "summary": "Comparison check was run.",
                    "refs": ["python3 docs/sejong/scripts/sejong_workflow_run.py check"],
                    "status": "verified",
                }
            )
            data["verification_evidence"] = ["comparison check was run"]
            data["status"] = "completed"
            data["final_recommendation"] = "reject"
            run_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            check = run_command(["check", "--path", str(run_path)])
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("quality_comparison acceptance_criteria must be a non-empty list once recorded", check.stderr)
            self.assertIn("completed run final_recommendation must match quality_comparison recommendation", check.stderr)

    def test_other_backend_requires_reviewable_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "weak-other",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "weak-other",
                    "--backend",
                    "other",
                    "--backend-summary",
                    "trust me",
                    "--command-ref",
                    "trust me",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Other backend provenance must be reviewable.",
                ]
            )
            self.assertNotEqual(start.returncode, 0)
            self.assertIn("backend other requires a specific backend_provenance summary", start.stderr)
            self.assertIn("backend other requires reviewable backend_provenance command_refs", start.stderr)

    def test_completed_run_requires_recorded_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "missing-comparison",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "deep_research",
                    "--workflow-name",
                    "missing-comparison",
                    "--backend",
                    "manual_shadow",
                    "--mapped-surface",
                    "jangyeongsil",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Comparison is recorded.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            complete = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "shadow comparison reviewed",
                    "--final-recommendation",
                    "keep_shadowing",
                ]
            )
            self.assertNotEqual(complete.returncode, 0)
            self.assertIn("completed run requires quality comparison recommendation", complete.stderr)

    def test_promote_requires_quality_to_justify_high_overhead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "weak-high-overhead",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "weak-high-overhead",
                    "--backend",
                    "codex_mock_workflow",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/VALIDATION.md",
                    "--success-criterion",
                    "Promotion quality justifies overhead.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            verification = run_command(
                [
                    "add-evidence",
                    "--path",
                    str(run_path),
                    "--evidence-id",
                    "verification-1",
                    "--kind",
                    "verification_ref",
                    "--summary",
                    "Verification command passed.",
                    "--ref",
                    "python3 docs/sejong/scripts/sejong_workflow_run.py check",
                    "--status",
                    "verified",
                ]
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)
            comparison = run_command(
                [
                    "record-comparison",
                    "--path",
                    str(run_path),
                    "--baseline-result-ref",
                    "baseline:weak-high-overhead",
                    "--candidate-result-ref",
                    "candidate:weak-high-overhead",
                    "--acceptance-criterion",
                    "Quality should justify overhead.",
                    "--outcome-quality-delta",
                    "0.0001",
                    "--overhead-ratio",
                    "999",
                    "--recommendation",
                    "promote",
                ]
            )
            self.assertEqual(comparison.returncode, 0, comparison.stderr)
            promote = run_command(
                [
                    "complete",
                    "--path",
                    str(run_path),
                    "--verification-evidence",
                    "shadow comparison complete",
                    "--final-recommendation",
                    "promote",
                ]
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("overhead_ratio > 1.25", promote.stderr)

    def test_claude_backend_is_not_a_valid_migration_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "bad-backend",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "bad-backend",
                    "--backend",
                    "claude_code_workflow",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Concepts are migrated to Codex-native or mocked equivalents.",
                ]
            )
            self.assertNotEqual(start.returncode, 0)
            self.assertIn("invalid choice", start.stderr)

    def test_hidden_claude_runtime_reference_is_rejected_even_with_other_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "hidden-runtime",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "Claude CLI runtime hidden behind other",
                    "--backend",
                    "other",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Hidden runtimes are blocked.",
                ]
            )
            self.assertNotEqual(start.returncode, 0)
            self.assertIn("hidden Claude runtime reference is forbidden", start.stderr)

    def test_other_backend_requires_explicit_non_claude_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "unapproved-other",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "dynamic_workflow",
                    "--workflow-name",
                    "unapproved-other",
                    "--backend",
                    "other",
                    "--mapped-surface",
                    "seungjeongwon",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Other backends need explicit provenance.",
                ]
            )
            self.assertNotEqual(start.returncode, 0)
            self.assertIn("backend_provenance summary must be a non-empty string", start.stderr)
            self.assertIn("backend_provenance command_refs must be a non-empty list", start.stderr)

    def test_worker_authority_paraphrase_in_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "authority-paraphrase",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "team_backend",
                    "--workflow-name",
                    "authority-paraphrase",
                    "--backend",
                    "team_executor",
                    "--mapped-surface",
                    "jiphyeonjeon",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Authority paraphrases are blocked.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            worker = run_command(
                [
                    "add-worker",
                    "--path",
                    str(run_path),
                    "--worker-id",
                    "paraphrase-worker",
                    "--role",
                    "review lane",
                    "--scope",
                    "worker majority approved the final decision",
                    "--allowed-output",
                    "bounded findings only",
                ]
            )
            self.assertNotEqual(worker.returncode, 0)
            self.assertIn("claims forbidden authority in scope", worker.stderr)

    def test_repo_local_runtime_path_requires_promotion_ref(self) -> None:
        run_path = REPO_ROOT / ".workflow-run-runtime-test.json"
        if run_path.exists():
            run_path.unlink()
        start = run_command(
            [
                "start",
                "--path",
                str(run_path),
                "--run-id",
                "repo-local-runtime",
                "--repo-root",
                ".",
                "--workflow-kind",
                "dynamic_workflow",
                "--workflow-name",
                "repo-local-runtime",
                "--backend",
                "codex_mock_workflow",
                "--mapped-surface",
                "seungjeongwon",
                "--source-of-truth-ref",
                "docs/sejong/ARTIFACT_STORAGE.md",
                "--success-criterion",
                "Runtime artifacts stay outside the repo unless promoted.",
            ]
        )
        self.assertNotEqual(start.returncode, 0)
        self.assertIn("repo-local workflow-run artifacts require --promoted-artifact-ref", start.stderr)
        self.assertFalse(run_path.exists())

    def test_schema_parity_rejects_extra_fields_and_bad_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "bad-schema-parity.json"
            data = {
                "format": "sejong.workflow-run/v0.1-draft",
                "run_id": "bad-schema-parity",
                "repo_root": ".",
                "status": "completed",
                "workflow_kind": "dynamic_workflow",
                "workflow_name": "bad-schema-parity",
                "mapped_surfaces": ["seungjeongwon"],
                "backend": "codex_mock_workflow",
                "backend_provenance": {
                    "migration_type": "codex_mock",
                    "non_claude_runtime": True,
                    "summary": "Codex mock only.",
                    "command_refs": ["mock:local"],
                },
                "mode": "shadow",
                "artifact_storage": {
                    "scope": "external",
                    "ref": "${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}",
                },
                "source_of_truth_refs": ["docs/sejong/DISCIPLINE_GATES.md"],
                "success_criteria": ["Schema parity"],
                "forbidden_authority_claims": [
                    "uigwe gate approval",
                    "final synthesis",
                    "final verification",
                    "consensus approval",
                    "majority-vote authority",
                ],
                "workers": [],
                "evidence_ledger": [
                    {
                        "evidence_id": "verification-1",
                        "kind": "verification_ref",
                        "summary": "Verified",
                        "refs": ["test"],
                        "status": "verified",
                    }
                ],
                "quality_comparison": {
                    "baseline_result_ref": "baseline",
                    "candidate_result_ref": "candidate",
                    "acceptance_criteria": ["same criteria"],
                    "outcome_quality_delta": 0.01,
                    "overhead_ratio": 1.0,
                    "recommendation": "keep_shadowing",
                },
                "metrics": {
                    "worker_count": 0,
                    "max_concurrency": 0,
                    "unsupported_claim_count": 0,
                    "token_or_cost_overhead_ref": "test",
                    "write_scopes_disjoint": True,
                },
                "verification_evidence": ["test"],
                "violations": [],
                "final_recommendation": "keep_shadowing",
                "created_at": "not-a-date",
                "updated_at": "2026-05-29T00:00:00Z",
                "extra": "not allowed",
            }
            run_path.write_text(json.dumps(data), encoding="utf-8")
            result = run_command(["check", "--path", str(run_path)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unexpected top-level field", result.stderr)
            self.assertIn("created_at must be a date-time string", result.stderr)

    def test_worker_forbidden_authority_claim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "workflow-run.json"
            start = run_command(
                [
                    "start",
                    "--path",
                    str(run_path),
                    "--run-id",
                    "authority-drift",
                    "--repo-root",
                    ".",
                    "--workflow-kind",
                    "team_backend",
                    "--workflow-name",
                    "bad-authority-worker",
                    "--backend",
                    "manual_shadow",
                    "--mapped-surface",
                    "jiphyeonjeon",
                    "--source-of-truth-ref",
                    "docs/sejong/DISCIPLINE_GATES.md",
                    "--success-criterion",
                    "Workers remain evidence-only.",
                ]
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            worker = run_command(
                [
                    "add-worker",
                    "--path",
                    str(run_path),
                    "--worker-id",
                    "worker-claims-too-much",
                    "--role",
                    "review lane",
                    "--scope",
                    "Review promotion candidate.",
                    "--allowed-output",
                    "final synthesis",
                ]
            )
            self.assertNotEqual(worker.returncode, 0)
            self.assertIn("claims forbidden authority", worker.stderr)


if __name__ == "__main__":
    unittest.main()
