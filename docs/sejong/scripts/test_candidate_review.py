#!/usr/bin/env python3
from __future__ import annotations

import unittest
from dataclasses import replace

from candidate_review import (
    CandidateEvidenceState,
    ReviewDispatchSpec,
    ReviewerLane,
    ReviewVerdict,
    build_review_dispatch,
    evaluate_candidate,
    review_receipt,
)
from discord_contract_types import ControlContractError, SandboxMode


class CandidateReviewTests(unittest.TestCase):
    def test_sol_dispatch_is_fresh_read_only_and_candidate_bound(self) -> None:
        # Given: a producer candidate and a distinct Sol reviewer run.
        spec = ReviewDispatchSpec(
            ticket_id="ticket-1",
            candidate_sha256="a" * 64,
            producer_run_id="luna-run-1",
            producer_actor_id="luna-implementer",
            reviewer_run_id="sol-run-1",
            reviewer_actor_id="sol-reviewer",
            reviewer_lane=ReviewerLane.SOL,
            reviewer_model="gpt-5.4",
            sandbox=SandboxMode.READ_ONLY,
            shadow=False,
        )

        # When: Core creates the review dispatch.
        dispatch = build_review_dispatch(spec)

        # Then: it is a new read-only run bound to the exact candidate.
        self.assertEqual(dispatch["candidate_sha256"], spec.candidate_sha256)
        self.assertEqual(dispatch["authority"], "approval_recommendation_only")
        self.assertEqual(dispatch["sandbox"], "read-only")
        self.assertNotEqual(dispatch["producer_run_id"], dispatch["reviewer_run_id"])

        # Given/When/Then: the producer cannot dispatch itself as approver.
        with self.assertRaises(ControlContractError) as raised:
            build_review_dispatch(replace(spec, reviewer_run_id=spec.producer_run_id))
        self.assertEqual(raised.exception.code, "self_review_forbidden")

        # Given/When/Then: a reviewer model must remain one opaque argv token.
        with self.assertRaises(ControlContractError) as model_error:
            build_review_dispatch(replace(spec, reviewer_model="gpt-5.4; touch /tmp/escaped"))
        self.assertEqual(model_error.exception.code, "unsafe_model")

    def test_antigravity_shadow_cannot_be_the_sole_approver(self) -> None:
        # Given: a candidate with only an Antigravity shadow opinion.
        dispatch = build_review_dispatch(ReviewDispatchSpec(
            ticket_id="ticket-1",
            candidate_sha256="b" * 64,
            producer_run_id="luna-run-1",
            producer_actor_id="luna-implementer",
            reviewer_run_id="antigravity-run-1",
            reviewer_actor_id="antigravity-reviewer",
            reviewer_lane=ReviewerLane.ANTIGRAVITY,
            reviewer_model="antigravity-model",
            sandbox=SandboxMode.READ_ONLY,
            shadow=True,
        ))
        receipt = review_receipt(
            dispatch,
            ReviewVerdict.APPROVED,
            evidence_refs=("artifact://shadow-review",),
            satisfied_requirements=("git diff --check",),
            unknowns=(),
        )

        # When: Core evaluates the candidate using only that second opinion.
        state = evaluate_candidate("b" * 64, (receipt,), ("git diff --check",))

        # Then: canonical approval remains pending.
        self.assertEqual(state, CandidateEvidenceState.REVIEW_PENDING)

    def test_exit_zero_without_independent_review_is_not_completion(self) -> None:
        # Given: producer evidence with no independent review receipt.
        # When: Core evaluates the candidate.
        state = evaluate_candidate("c" * 64, (), ("git diff --check",))

        # Then: process success alone cannot cross the review gate.
        self.assertEqual(state, CandidateEvidenceState.REVIEW_PENDING)

    def test_dispatch_and_review_receipt_seals_block_changed_approval(self) -> None:
        # Given: a valid fresh Sol dispatch and approval evidence.
        dispatch = build_review_dispatch(ReviewDispatchSpec(
            ticket_id="ticket-1",
            candidate_sha256="d" * 64,
            producer_run_id="luna-run-1",
            producer_actor_id="luna-implementer",
            reviewer_run_id="sol-run-1",
            reviewer_actor_id="sol-reviewer",
            reviewer_lane=ReviewerLane.SOL,
            reviewer_model="gpt-5.4",
            sandbox=SandboxMode.READ_ONLY,
            shadow=False,
        ))
        receipt = review_receipt(
            dispatch,
            ReviewVerdict.APPROVED,
            evidence_refs=("artifact://sol-review",),
            satisfied_requirements=("git diff --check",),
            unknowns=(),
        )

        # When/Then: sealed valid evidence can produce an approval recommendation.
        self.assertEqual(len(dispatch["dispatch_sha256"]), 64)
        self.assertEqual(len(receipt["receipt_sha256"]), 64)
        self.assertEqual(
            evaluate_candidate("d" * 64, (receipt,), ("git diff --check",)),
            CandidateEvidenceState.REVIEW_APPROVED,
        )

        # When/Then: changing either sealed artifact cannot forge approval.
        forged_receipt = dict(receipt)
        forged_receipt["reviewer_actor_id"] = "luna-implementer"
        with self.assertRaises(ControlContractError) as receipt_error:
            evaluate_candidate("d" * 64, (forged_receipt,), ("git diff --check",))
        self.assertEqual(receipt_error.exception.code, "invalid_review_receipt")
        forged_dispatch = dict(dispatch)
        forged_dispatch["reviewer_actor_id"] = "luna-implementer"
        with self.assertRaises(ControlContractError) as dispatch_error:
            review_receipt(
                forged_dispatch,
                ReviewVerdict.APPROVED,
                evidence_refs=("artifact://forged",),
                satisfied_requirements=("git diff --check",),
                unknowns=(),
            )
        self.assertEqual(dispatch_error.exception.code, "invalid_review_dispatch")


if __name__ == "__main__":
    unittest.main()
