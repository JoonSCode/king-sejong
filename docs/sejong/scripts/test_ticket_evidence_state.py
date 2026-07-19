#!/usr/bin/env python3
from __future__ import annotations

import unittest

from candidate_review import CandidateEvidenceState
from ticket_evidence_state import CoreVerification, TicketState, reduce_ticket_state


class TicketEvidenceStateTests(unittest.TestCase):
    def test_sol_approval_still_requires_core_final_verification(self) -> None:
        # Given: an independently approved candidate without a Core verification receipt.
        # When: Core reduces the canonical ticket state.
        state = reduce_ticket_state(
            "a" * 64,
            CandidateEvidenceState.REVIEW_APPROVED,
            ("git diff --check",),
            None,
        )

        # Then: reviewer recommendation alone is not completion.
        self.assertEqual(state["state"], TicketState.FINAL_VERIFICATION_PENDING.value)
        self.assertFalse(state["completion_eligible"])

    def test_only_matching_core_evidence_can_mark_candidate_verified(self) -> None:
        # Given: Sol approval plus a candidate-bound Core verification receipt.
        verification = CoreVerification(
            candidate_sha256="b" * 64,
            verifier_run_id="core-verifier-1",
            satisfied_requirements=("git diff --check",),
            evidence_refs=("receipt://core-final-check",),
            passed=True,
        )

        # When: Core performs the final state reduction.
        state = reduce_ticket_state(
            "b" * 64,
            CandidateEvidenceState.REVIEW_APPROVED,
            ("git diff --check",),
            verification,
        )

        # Then: the evidence-based state is verified under Core authority.
        self.assertEqual(state["state"], TicketState.VERIFIED.value)
        self.assertTrue(state["completion_eligible"])
        self.assertEqual(state["completion_authority"], "core_final_verification")


if __name__ == "__main__":
    unittest.main()
