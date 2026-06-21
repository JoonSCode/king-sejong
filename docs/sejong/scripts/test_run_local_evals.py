#!/usr/bin/env python3
from __future__ import annotations

import unittest

import run_local_evals


class RunLocalEvalsTests(unittest.TestCase):
    def test_default_steps_cover_required_eval_pack_without_writes(self) -> None:
        steps = run_local_evals.build_steps(write_scorecards=False, include_install_verify=False)
        step_ids = [step.step_id for step in steps]
        self.assertEqual(
            step_ids,
            [
                "hook-tests",
                "context-tests",
                "seungjeongwon-run-tests",
                "sillok-trace-tests",
                "cleanup-tests",
                "e2e-tests",
                "sejong-surface-benchmark",
                "instruction-surface-benchmark",
                "json-contracts",
                "sandbox-claim-guard",
            ],
        )
        commands = [" ".join(step.command) for step in steps]
        self.assertTrue(any("test_king_sejong_hooks.py" in command for command in commands))
        self.assertTrue(any("benchmark_sejong_surface.py --require-targets" in command for command in commands))
        self.assertTrue(any("benchmark_instruction_surface.py --require-targets" in command for command in commands))
        self.assertTrue(any("validate_json_contracts.py" in command for command in commands))
        self.assertTrue(any("check-sandbox-claims" in command for command in commands))
        self.assertFalse(any("--write" in command for command in commands))

    def test_write_scorecards_and_install_verify_are_explicit(self) -> None:
        steps = run_local_evals.build_steps(write_scorecards=True, include_install_verify=True)
        commands = [" ".join(step.command) for step in steps]
        self.assertTrue(any("benchmark_sejong_surface.py --write --require-targets" in command for command in commands))
        self.assertTrue(
            any("benchmark_instruction_surface.py --write --require-targets" in command for command in commands)
        )
        self.assertEqual(steps[-1].step_id, "repo-install-verify")
        self.assertIn("scripts/install-sejong.sh --verify .", " ".join(steps[-1].command))

    def test_e2e_step_uses_external_temp_sejong_home(self) -> None:
        steps = run_local_evals.build_steps(write_scorecards=False, include_install_verify=False)
        e2e = next(step for step in steps if step.step_id == "e2e-tests")
        self.assertTrue(e2e.temp_sejong_home)


if __name__ == "__main__":
    unittest.main()
