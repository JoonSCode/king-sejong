#!/usr/bin/env python3
from __future__ import annotations

import unittest
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bounded_worker_brief import BRIEF_FORMAT, validate_bounded_worker_brief


def valid_brief() -> dict:
    return {
        "format": BRIEF_FORMAT,
        "objective": "Produce bounded verification evidence.",
        "role": "verifier",
        "source_of_truth_refs": ["brief.md"],
        "allowed_outputs": ["bounded evidence refs", "verification observations", "blockers"],
        "forbidden_claims": [
            "Uigwe gate approval",
            "final synthesis",
            "final verification",
            "majority-vote authority",
            "consensus approval",
            "scope widening",
        ],
        "write_scope": ["none"],
        "stop_condition": "Return to the Sejong lead after evidence or blocker.",
        "evidence_refs": ["brief.md"],
    }


class BoundedWorkerBriefTests(unittest.TestCase):
    def test_valid_brief_passes(self) -> None:
        self.assertEqual(validate_bounded_worker_brief(valid_brief(), expected_source_of_truth_refs=["brief.md"]), [])

    def test_missing_v2_fields_fail(self) -> None:
        brief = valid_brief()
        del brief["objective"]
        del brief["write_scope"]
        del brief["evidence_refs"]

        failures = validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"])

        self.assertIn("worker brief missing objective", failures)
        self.assertIn("worker brief missing write_scope", failures)
        self.assertIn("worker brief missing evidence_refs", failures)

    def test_missing_expected_source_ref_fails(self) -> None:
        brief = valid_brief()
        brief["source_of_truth_refs"] = ["other.md"]

        failures = validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"])

        self.assertIn("worker brief source_of_truth_refs missing expected refs: ['brief.md']", failures)

    def test_authority_claim_in_allowed_output_fails(self) -> None:
        brief = valid_brief()
        brief["allowed_outputs"] = ["approve the Uigwe gate"]

        failures = validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"])

        self.assertIn("worker brief allowed_outputs claims forbidden authority: approve the uigwe gate", failures)

    def test_team_worker_state_format_passes(self) -> None:
        brief = valid_brief()
        brief["format"] = "sejong.team-worker/v0.1-draft"
        brief["forbidden_worker_claims"] = brief.pop("forbidden_claims")

        self.assertEqual(validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"]), [])

    def test_hidden_external_runtime_write_scope_fails(self) -> None:
        brief = valid_brief()
        brief["write_scope"] = [".external-runtime/state.json"]

        failures = validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"])

        self.assertIn(
            "worker brief write_scope must not depend on hidden external runtime state: .external-runtime/state.json",
            failures,
        )

    def test_known_repo_hidden_write_scope_roots_pass(self) -> None:
        brief = valid_brief()
        brief["write_scope"] = [".agents/skills/example", ".codex/prompts/reviewer.md", ".github/workflows/ci.yml"]

        self.assertEqual(validate_bounded_worker_brief(brief, expected_source_of_truth_refs=["brief.md"]), [])


if __name__ == "__main__":
    unittest.main()
