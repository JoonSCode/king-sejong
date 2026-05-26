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
GATE = SEJONG_ROOT / "scripts" / "sejong_integrated_quality_gate.py"


class SejongIntegratedQualityGateTests(unittest.TestCase):
    def test_latest_sot_and_enhancements_work_together_for_tagback_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE),
                    "--sejong-root",
                    str(SEJONG_ROOT),
                    "--work-dir",
                    tmp,
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.integrated-quality-gate/v0.1-draft")
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["goal"], "tagback-growth")
        self.assertGreaterEqual(payload["quality_delta"], 0.12)
        check_ids = {check["id"] for check in payload["checks"]}
        self.assertIn("outcome_quality_promotes_candidate", check_ids)
        self.assertIn("research_to_uigwe_gate_blocks_write", check_ids)
        self.assertIn("seungjeongwon_active_run_blocks_stop_until_verified", check_ids)
        self.assertIn("team_persuasion_round_uses_existing_mailbox_contract", check_ids)
        self.assertIn("visible_todo_and_paired_result_feedback_still_present", check_ids)
        self.assertIn("product_evidence_gate_requires_external_success_evidence", check_ids)


if __name__ == "__main__":
    unittest.main()
