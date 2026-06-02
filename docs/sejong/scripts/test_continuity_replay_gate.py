#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "continuity_replay_gate.py"
CONTEXT_EXAMPLE = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"
CAPSULE_EXAMPLE = SEJONG_ROOT / "examples" / "continuity-capsule.example.json"


def run_gate(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class ContinuityReplayGateTests(unittest.TestCase):
    def test_replay_gate_proves_postcompact_working_set_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_EXAMPLE.read_text(encoding="utf-8"))
            capsule_path = Path(tmp) / "continuity-capsule.json"
            capsule = json.loads(CAPSULE_EXAMPLE.read_text(encoding="utf-8"))
            capsule["repo_root"] = str(REPO_ROOT)
            capsule_path.write_text(json.dumps(capsule), encoding="utf-8")
            context["repo_root"] = str(REPO_ROOT)
            context["task_class"] = "runtime-contract-design"
            context["projection_profile"] = "frontier"
            context["artifact_refs"] = [str(capsule_path)]
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            result = run_gate(
                [
                    "judge",
                    "--context",
                    str(context_path),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--require",
                    "continuity_capsule=capsule-continuity-example",
                    "--require",
                    "continuity_decision=Use a continuity capsule",
                    "--require",
                    "continuity_rejected=Use only markdown handoff",
                    "--forbid",
                    "Replay full trace history",
                    "--max-chars",
                    "2500",
                ]
            )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertLessEqual(payload["projection_chars"], 2500)

    def test_replay_gate_materializes_context_local_capsule_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_EXAMPLE.read_text(encoding="utf-8"))
            capsule_path = Path(tmp) / "continuity-capsule.example.json"
            capsule = json.loads(CAPSULE_EXAMPLE.read_text(encoding="utf-8"))
            capsule["repo_root"] = str(REPO_ROOT)
            capsule_path.write_text(json.dumps(capsule), encoding="utf-8")
            context["repo_root"] = str(REPO_ROOT)
            context["task_class"] = "runtime-contract-design"
            context["projection_profile"] = "frontier"
            context["artifact_refs"] = [capsule_path.name]
            context_path = Path(tmp) / "continuity-context.example.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            result = run_gate(
                [
                    "judge",
                    "--context",
                    str(context_path),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--require",
                    "continuity_capsule=capsule-continuity-example",
                    "--max-chars",
                    "2500",
                ]
            )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])

    def test_replay_gate_fails_when_required_state_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = json.loads(CONTEXT_EXAMPLE.read_text(encoding="utf-8"))
            context["repo_root"] = str(REPO_ROOT)
            context["artifact_refs"] = []
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(context), encoding="utf-8")

            result = run_gate(
                [
                    "judge",
                    "--context",
                    str(context_path),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--require",
                    "continuity_capsule=",
                ]
            )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])


if __name__ == "__main__":
    unittest.main()
