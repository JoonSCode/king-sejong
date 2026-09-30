#!/usr/bin/env python3
"""Focused CLI regressions for comparable scorecards and explicit cost bounds."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("compare_scorecards.py")


def card(tokens: int | None = 100, scores: tuple[float, ...] = (1.0,)) -> dict:
    results = [
        {"scenario_id": f"case-{index}", "status": "pass" if score == 1 else "partial", "score": score}
        for index, score in enumerate(scores)
    ]
    value = {
        "metadata": {"id": "card", "task_set_id": "frozen-set"},
        "aggregate": {
            "scenario_count": len(results),
            "pass_count": sum(item["status"] == "pass" for item in results),
            "partial_count": sum(item["status"] == "partial" for item in results),
            "fail_count": 0,
            "average_score": round(sum(scores) / len(scores), 4),
        },
        "scenario_results": results,
    }
    if tokens is not None:
        value["resource_usage"] = {"total_tokens": tokens}
    return value


class ComparisonTests(unittest.TestCase):
    def run_cli(self, baseline: dict, candidate: dict, *flags: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in ("baseline.json", "candidate.json")]
            snapshots = [json.dumps(value).encode() for value in (baseline, candidate)]
            for path, snapshot in zip(paths, snapshots):
                path.write_bytes(snapshot)
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), *(str(path) for path in paths), *flags],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual([path.read_bytes() for path in paths], snapshots)
            return result

    def assert_invalid(self, baseline: dict, candidate: dict, *flags: str) -> None:
        result = self.run_cli(baseline, candidate, *flags)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Invalid comparison", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_normal_and_rounded_average(self) -> None:
        result = self.run_cli(card(100, (1, 0.3333, 0.6667)), card(80, (1, 0.3333, 0.6667)),
                              "--require-non-regression", "--max-token-ratio", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("token_ratio=0.8000", result.stdout)
        self.assertIn("cost_ratio=unknown", result.stdout)
        self.assertIn("cost_normalized_gain=unknown", result.stdout)

    def test_usage_missing_quality_only_and_bounded(self) -> None:
        for side in (0, 1):
            for missing in ("usage", "total"):
                with self.subTest(side=side, missing=missing):
                    cards = [card(), card()]
                    if missing == "usage":
                        cards[side].pop("resource_usage")
                    else:
                        cards[side]["resource_usage"].pop("total_tokens")
                    result = self.run_cli(*cards, "--require-non-regression")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("token_ratio=unknown", result.stdout)
                    bounded = self.run_cli(*cards, "--max-token-ratio", "1")
                    self.assertNotEqual(bounded.returncode, 0, bounded.stdout)
                    self.assertIn("token_ratio=unknown", bounded.stdout)
                    self.assertNotIn("token_ratio=0.0000", bounded.stdout)
        result = self.run_cli(card(None), card(None), "--max-token-ratio", "1")
        self.assertNotEqual(result.returncode, 0)

    def test_zero_baseline_and_real_zero_candidate(self) -> None:
        result = self.run_cli(card(0), card(0), "--max-token-ratio", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("token_ratio=undefined", result.stdout)
        result = self.run_cli(card(100), card(0), "--max-token-ratio", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("token_ratio=0.0000", result.stdout)

    def test_token_bound_independent_of_quality_flag(self) -> None:
        result = self.run_cli(card(100), card(120), "--max-token-ratio", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exceeded", result.stdout)

    def test_quality_regression_flag(self) -> None:
        result = self.run_cli(card(), card(80, (0.5,)), "--require-non-regression")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scenario_regressions=1", result.stdout)
        self.assertEqual(self.run_cli(card(), card(80, (0.5,))).returncode, 0)

    def test_invalid_usage_and_bound(self) -> None:
        for side in (0, 1):
            for value in (-1, True, "80", 0.5, None, float("nan"), float("inf")):
                with self.subTest(side=side, value=value):
                    cards = [card(), card()]
                    cards[side]["resource_usage"]["total_tokens"] = value
                    self.assert_invalid(*cards)
        for value in (-1, True, "1", float("nan"), float("inf")):
            candidate = card()
            candidate["resource_usage"]["estimated_cost_usd"] = value
            self.assert_invalid(card(), candidate)
        for bound in ("-1", "nan", "inf"):
            self.assert_invalid(card(), card(), "--max-token-ratio", bound)

    def test_duplicate_scenarios_rejected_on_both_sides(self) -> None:
        for side in (0, 1):
            cards = [card(), card()]
            cards[side]["scenario_results"].append(copy.deepcopy(cards[side]["scenario_results"][0]))
            self.assert_invalid(*cards)

    def test_incomparable_task_sets_and_scenarios(self) -> None:
        candidate = card()
        candidate["metadata"]["task_set_id"] = "other-set"
        self.assert_invalid(card(), candidate)
        self.assert_invalid(card(), card(scores=(1, 1)))
        self.assert_invalid(card(scores=(1, 1)), card())

    def test_malformed_scenarios_and_aggregate(self) -> None:
        mutations = (
            ("scenario_results", []), ("scenario_results", {}),
            ("scenario_results", [None]), ("metadata", []), ("aggregate", []),
        )
        for key, value in mutations:
            candidate = card()
            candidate[key] = value
            self.assert_invalid(card(), candidate)
        for key, value in (("scenario_id", ""), ("status", "unknown"), ("score", True),
                           ("score", float("nan")), ("score", 2)):
            candidate = card()
            candidate["scenario_results"][0][key] = value
            self.assert_invalid(card(), candidate)
        for key in ("scenario_count", "pass_count", "partial_count", "fail_count", "average_score"):
            candidate = card()
            candidate["aggregate"][key] = 0.5 if key == "average_score" else 9
            self.assert_invalid(card(), candidate)

    def test_known_cost_ratio(self) -> None:
        baseline, candidate = card(), card(80)
        baseline["resource_usage"]["estimated_cost_usd"] = 2
        candidate["resource_usage"]["estimated_cost_usd"] = 1
        result = self.run_cli(baseline, candidate)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cost_ratio=0.5000", result.stdout)


if __name__ == "__main__":
    unittest.main()
