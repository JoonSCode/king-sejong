#!/usr/bin/env python3
from __future__ import annotations

import unittest
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))
from ux_profile_contract import ux_profile_failures


def valid_output() -> dict:
    return {
        "format": "sejong.ux-profile-output/v0.1-draft",
        "profile": "bounded-specialist-evidence",
        "owner_surface": "jangyeongsil",
        "next_surface": "uigwe",
        "claim_type": "evidence",
        "known": ["The specialist inspected a bounded evidence scope."],
        "inferred": ["The result can inform Uigwe readiness."],
        "unknown": ["Whether the user approves the plan."],
        "forbidden_claims": ["no_gate_approval", "no_execution_approval", "no_completion_claim"],
    }


class UxProfileContractTests(unittest.TestCase):
    def test_valid_profile_output_passes(self) -> None:
        self.assertEqual(ux_profile_failures(valid_output()), [])

    def test_rejects_gate_approval_claims(self) -> None:
        payload = valid_output()
        payload["known"].append("The worker can approve Uigwe gate.")
        failures = ux_profile_failures(payload)
        self.assertTrue(any("forbidden authority term" in failure for failure in failures))

    def test_rejects_completion_claims(self) -> None:
        payload = valid_output()
        payload["completion_claim"] = True
        failures = ux_profile_failures(payload)
        self.assertIn("profile output cannot claim completion", failures)

    def test_rejects_missing_required_forbidden_claims(self) -> None:
        payload = valid_output()
        payload["forbidden_claims"] = ["no_gate_approval"]
        failures = ux_profile_failures(payload)
        self.assertTrue(any("missing required forbidden_claims" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
