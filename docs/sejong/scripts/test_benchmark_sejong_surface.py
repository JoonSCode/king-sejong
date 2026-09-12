#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

import benchmark_sejong_surface as benchmark


class RoutingExpectationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = benchmark.load_json(benchmark.TASK_SET_PATH)["scenarios"]
        self.fixture = copy.deepcopy(self.scenarios[0])
        self.fixture.update(
            expected_route_sequence=["seungjeongwon"],
            acceptable_route_sequences=[["seungjeongwon"]],
            forbidden_surfaces=["uigwe", "sejong-direct"],
            guardrail_expectations={"required_route_sequence": ["seungjeongwon"]},
        )

    def test_settled_execution_expectation_is_consistent(self) -> None:
        self.assertEqual(benchmark.evaluate_scenario(self.fixture)["status"], "pass")

    def test_forbidden_uigwe_cannot_be_an_acceptable_alternative(self) -> None:
        self.fixture["acceptable_route_sequences"].append(["uigwe", "seungjeongwon"])
        self.assertNotEqual(benchmark.evaluate_scenario(self.fixture)["status"], "pass")

    def test_required_execution_cannot_be_omitted_by_an_alternative(self) -> None:
        self.fixture["acceptable_route_sequences"].append(["jangyeongsil"])
        self.assertNotEqual(benchmark.evaluate_scenario(self.fixture)["status"], "pass")

    def test_primary_route_must_be_accepted(self) -> None:
        self.fixture["expected_route_sequence"] = ["jangyeongsil", "seungjeongwon"]
        self.assertNotEqual(benchmark.evaluate_scenario(self.fixture)["status"], "pass")

    def test_seed_distinguishes_settled_and_unresolved_implementation(self) -> None:
        scenarios = {item["id"]: item for item in self.scenarios}
        self.assertIn("route-settled-implementation-no-bundle", scenarios)
        settled = scenarios["route-settled-implementation-no-bundle"]
        self.assertEqual(settled["expected_route_sequence"], ["seungjeongwon"])
        self.assertIn("uigwe", settled["forbidden_surfaces"])
        unresolved = scenarios["route-goal-bearing-unresolved-handoff"]
        self.assertTrue(unresolved["clarification_required"])
        self.assertEqual(unresolved["expected_route_sequence"], ["uigwe", "seungjeongwon"])


if __name__ == "__main__":
    unittest.main()
