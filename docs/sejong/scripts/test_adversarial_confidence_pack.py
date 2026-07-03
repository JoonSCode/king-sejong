#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "run_adversarial_confidence_pack.py"


class AdversarialConfidencePackTests(unittest.TestCase):
    def test_pack_runs_required_scenarios(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER)],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        scenario_ids = [scenario["scenario_id"] for scenario in payload["scenarios"]]
        self.assertEqual(
            scenario_ids,
            [
                "bare-native-goal-receipt-rejected",
                "missing-env-context-no-fallback",
                "interpreter-write-bypass-rejected",
                "team-duplicate-message-rejected",
            ],
        )


if __name__ == "__main__":
    unittest.main()
