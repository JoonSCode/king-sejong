#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "audit_workflow_run_risks.py"
sys.path.insert(0, str(SEJONG_ROOT / "scripts"))
from benchmark_workflow_run import valid_cases  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class WorkflowRunRiskAuditTests(unittest.TestCase):
    def test_audit_passes_with_strict_local_refs_and_promoted_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "evidence" / "baseline.md"
            candidate = root / "evidence" / "candidate.md"
            baseline.parent.mkdir(parents=True)
            baseline.write_text("baseline result\n", encoding="utf-8")
            candidate.write_text("candidate result\n", encoding="utf-8")
            source_ref = root / "docs" / "sejong" / "DISCIPLINE_GATES.md"
            source_ref.parent.mkdir(parents=True)
            source_ref.write_text("source of truth\n", encoding="utf-8")

            data = deepcopy(valid_cases()[1])
            data["repo_root"] = str(root)
            data["quality_comparison"]["baseline_result_ref"] = "evidence/baseline.md"
            data["quality_comparison"]["candidate_result_ref"] = "evidence/candidate.md"
            artifact = root / "promoted" / "workflow-run.json"
            data["artifact_storage"] = {"scope": "promoted_repo_artifact", "ref": "promoted/workflow-run.json"}
            write_json(artifact, data)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--repo-root",
                    str(root),
                    "--artifact",
                    str(artifact),
                    "--strict-local-refs",
                    "--require-promoted",
                    "--json",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["promoted_count"], 1)

    def test_audit_fails_symbolic_refs_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = deepcopy(valid_cases()[1])
            data["repo_root"] = str(root)
            data["artifact_storage"] = {"scope": "promoted_repo_artifact", "ref": "workflow-run.json"}
            artifact = root / "workflow-run.json"
            write_json(artifact, data)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--repo-root",
                    str(root),
                    "--artifact",
                    str(artifact),
                    "--strict-local-refs",
                    "--json",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["passed"])
            self.assertTrue(any("baseline_result_ref must resolve" in failure for failure in payload["failures"]))

    def test_audit_fails_unpromoted_repo_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = deepcopy(valid_cases()[0])
            data["repo_root"] = str(root)
            data["artifact_storage"] = {"scope": "external", "ref": "~/.codex/sejong"}
            artifact = root / "workflow-run.json"
            write_json(artifact, data)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--repo-root",
                    str(root),
                    "--artifact",
                    str(artifact),
                    "--json",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["passed"])
            self.assertTrue(any("repo-local workflow-run artifact" in failure for failure in payload["failures"]))

    def test_audit_fails_when_required_corpus_diversity_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = deepcopy(valid_cases()[0])
            data["repo_root"] = str(root)
            data["artifact_storage"] = {"scope": "promoted_repo_artifact", "ref": "workflow-run.json"}
            artifact = root / "workflow-run.json"
            write_json(artifact, data)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--repo-root",
                    str(root),
                    "--artifact",
                    str(artifact),
                    "--min-artifacts",
                    "2",
                    "--min-workflow-kinds",
                    "2",
                    "--min-backends",
                    "2",
                    "--json",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["passed"])
            self.assertTrue(any("expected at least 2" in failure for failure in payload["failures"]))


if __name__ == "__main__":
    unittest.main()
