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
GATE = SEJONG_ROOT / "scripts" / "product_evidence_gate.py"
FIXTURE_ROOT = SEJONG_ROOT / "examples" / "outcome-evaluation" / "tagback-growth"


def run_gate(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class ProductEvidenceGateTests(unittest.TestCase):
    def test_tagback_field_validation_plan_is_ready_but_not_success_claim(self) -> None:
        result = run_gate(["check-plan", "--plan", str(FIXTURE_ROOT / "field-validation-plan.json")])
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.product-evidence-judgment/v0.1-draft")
        self.assertEqual(payload["status"], "ready_for_field_test")
        self.assertFalse(payload["can_claim_product_success"])
        self.assertIn("controlled_experiment", payload["validated_evidence_classes"])
        self.assertIn("user_research", payload["validated_evidence_classes"])
        self.assertIn("analytics", payload["validated_evidence_classes"])

    def test_success_claim_fails_without_external_result_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_result = Path(tmp) / "empty-result.json"
            empty_result.write_text(
                json.dumps(
                    {
                        "format": "sejong.product-evidence-result/v0.1-draft",
                        "task_id": "tagback-growth",
                        "result_id": "empty",
                        "collected_at": "2026-05-26T00:00:00Z",
                        "external_evidence_refs": [],
                        "analytics": {},
                        "controlled_experiment": {},
                        "user_research": {},
                    }
                ),
                encoding="utf-8",
            )
            result = run_gate(
                [
                    "judge-result",
                    "--plan",
                    str(FIXTURE_ROOT / "field-validation-plan.json"),
                    "--result",
                    str(empty_result),
                    "--require-success",
                ]
            )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "insufficient_evidence")
        self.assertFalse(payload["can_claim_product_success"])
        self.assertIn("external evidence refs are required", " ".join(payload["failures"]))

    def test_tagback_success_fixture_supports_success_claim(self) -> None:
        result = run_gate(
            [
                "judge-result",
                "--plan",
                str(FIXTURE_ROOT / "field-validation-plan.json"),
                "--result",
                str(FIXTURE_ROOT / "field-validation-result.example.json"),
                "--require-success",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "success_supported")
        self.assertTrue(payload["can_claim_product_success"])
        self.assertGreaterEqual(payload["score"], 1.0)
        self.assertEqual(payload["task_id"], "tagback-growth")


if __name__ == "__main__":
    unittest.main()
