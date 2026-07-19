#!/usr/bin/env python3
from __future__ import annotations

import unittest
import math
from dataclasses import replace

from discord_contract_types import RiskClass
from discord_contract_types import ControlContractError
from discord_model_policy import (
    ModelPolicy,
    PromotionState,
    RoutingRequest,
    ShadowMetrics,
    evaluate_shadow_promotion,
    route_ticket,
)


class DiscordModelPolicyTests(unittest.TestCase):
    def test_route_uses_task_risk_and_verification_with_router_only_terra(self) -> None:
        # Given: Core model slots and a high-risk implementation ticket.
        policy = ModelPolicy(
            luna_model="gpt-5.4",
            sol_model="gpt-5.4",
            antigravity_model="antigravity-shadow",
        )
        request = RoutingRequest(
            task_class="implementation",
            risk_class=RiskClass.HIGH,
            verification_class="release",
        )

        # When: Core routes by the ticket classification.
        decision = route_ticket(policy, request)

        # Then: Terra remains non-mutating while Luna and Sol receive fixed run models.
        self.assertEqual(decision["controller"]["slot"], "terra")
        self.assertFalse(decision["controller"]["can_mutate"])
        self.assertEqual(decision["implementer"]["slot"], "luna")
        self.assertEqual(decision["implementer"]["model"], policy.luna_model)
        self.assertEqual(decision["reviewer"]["slot"], "sol")
        self.assertEqual(decision["reviewer"]["sandbox"], "read-only")
        self.assertTrue(decision["requires_approval"])
        self.assertEqual(decision["verification_class"], request.verification_class)

    def test_shadow_lane_never_promotes_automatically(self) -> None:
        # Given: favorable shadow metrics but no explicit promotion approval.
        metrics = ShadowMetrics(
            task_class="implementation",
            comparable_runs=5,
            independent_reviews=5,
            quality_delta=0.2,
            regressions=0,
            approval_ref=None,
        )

        # When: Core evaluates the shadow lane.
        decision = evaluate_shadow_promotion(metrics)

        # Then: evidence without approval remains shadow, never automatically active.
        self.assertEqual(decision.state, PromotionState.SHADOW)
        self.assertFalse(decision.automatic_promotion)

        # When/Then: explicit approval can create a candidate, but still not auto-activate it.
        approved = evaluate_shadow_promotion(replace(metrics, approval_ref="approval://core-review"))
        self.assertEqual(approved.state, PromotionState.PROMOTION_CANDIDATE)
        self.assertFalse(approved.automatic_promotion)

    def test_non_finite_shadow_metrics_cannot_create_promotion_candidate(self) -> None:
        # Given: otherwise qualifying evidence with a non-finite quality delta.
        metrics = ShadowMetrics(
            task_class="implementation",
            comparable_runs=3,
            independent_reviews=3,
            quality_delta=math.nan,
            regressions=0,
            approval_ref="approval://core-review",
        )

        # When: Core evaluates the metric boundary.
        decision = evaluate_shadow_promotion(metrics)

        # Then: malformed numeric evidence stays shadow.
        self.assertEqual(decision.state, PromotionState.SHADOW)
        self.assertIn("invalid_metrics", decision.reasons)

    def test_core_policy_rejects_model_tokens_that_cannot_be_one_argv_element(self) -> None:
        # Given: a Core policy model containing shell composition syntax.
        policy = ModelPolicy("gpt-5.4; touch /tmp/escaped", "gpt-5.4", "shadow-model")

        # When/Then: routing rejects it before a ticket process can be built.
        with self.assertRaises(ControlContractError) as raised:
            route_ticket(policy, RoutingRequest("implementation", RiskClass.LOW, "targeted"))
        self.assertEqual(raised.exception.code, "unsafe_model")


if __name__ == "__main__":
    unittest.main()
