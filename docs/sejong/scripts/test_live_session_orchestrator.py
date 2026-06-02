#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from live_session_orchestrator import evaluate_live_session


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ORCHESTRATOR_SCRIPT = SCRIPT_PATH.parent / "live_session_orchestrator.py"


def incomplete_full_state() -> dict:
    return {
        "mode": "full",
        "profile": "greenfield",
        "live_session": True,
        "active_context_id": "ctx-live-test",
        "route_id": "route-live-test",
        "ambiguity_register_id": "amb-live-test",
        "last_updated_at": "2026-06-02T00:00:00Z",
        "intent": {
            "goal": "Harden Uigwe live-session runtime gates.",
            "why_now": "",
            "in_scope": [],
            "non_goals": [],
            "decision_boundaries": [],
            "constraints": [],
            "acceptance_criteria": [],
            "open_questions": ["Which user decisions must block the next stage?"],
        },
        "design": {},
    }


class LiveSessionOrchestratorTests(unittest.TestCase):
    def test_evaluate_live_session_builds_pending_ambiguity_register(self) -> None:
        result = evaluate_live_session(incomplete_full_state())

        register = result["ambiguity_register"]
        self.assertEqual(register["format"], "sejong.ambiguity-register/v0.1-draft")
        self.assertEqual(register["metadata"]["id"], "amb-live-test")
        self.assertEqual(register["stage_id"], "intent_clarification")
        self.assertEqual(register["stage_label"], "기획 명확화")
        self.assertLess(register["readiness_percent"], 100)
        self.assertEqual(register["blocking_count"], len(register["ambiguities"]))
        self.assertGreater(register["blocking_count"], 0)
        self.assertEqual(register["ambiguities"][0]["status"], "pending")
        self.assertTrue(register["ambiguities"][0]["free_response_allowed"])
        self.assertIn("next stage", register["next_required_user_action"])

    def test_evaluate_live_session_builds_codex_structured_choice_requests(self) -> None:
        result = evaluate_live_session(incomplete_full_state())

        requests = result["structured_choice_requests"]
        self.assertGreater(len(requests), 0)
        first_request = requests[0]
        self.assertEqual(first_request["adapter"], "codex_structured_choice")
        self.assertEqual(first_request["id"], result["ambiguity_register"]["ambiguities"][0]["id"])
        self.assertEqual(first_request["question"], result["ambiguity_register"]["ambiguities"][0]["question"])
        self.assertTrue(first_request["free_response_allowed"])
        self.assertTrue(first_request["options"][0]["label"].endswith("(Recommended)"))

    def test_cli_writes_ambiguity_register_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "state.json"
            output_path = Path(tmp) / "ambiguity-register.json"
            input_path.write_text(json.dumps(incomplete_full_state()), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ORCHESTRATOR_SCRIPT),
                    str(input_path),
                    "--json",
                    "--write-register",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "sejong.ambiguity-register/v0.1-draft")
            self.assertEqual(payload["metadata"]["active_context_id"], "ctx-live-test")
            stdout = json.loads(result.stdout)
            self.assertEqual(stdout["ambiguity_register_path"], str(output_path))


if __name__ == "__main__":
    unittest.main()
