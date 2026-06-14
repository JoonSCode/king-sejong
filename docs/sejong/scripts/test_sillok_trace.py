#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
SILLOK_TRACE = SEJONG_ROOT / "scripts" / "sillok_trace.py"


def run_sillok(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SILLOK_TRACE), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )


class SillokTraceTests(unittest.TestCase):
    def test_trace_append_and_check_passes_for_bounded_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "sillok-record.jsonl"
            append = run_sillok(
                [
                    "append",
                    "--trace",
                    str(trace),
                    "--run-id",
                    "run-test",
                    "--active-context-id",
                    "ctx-test",
                    "--surface",
                    "jangyeongsil",
                    "--event-kind",
                    "security_review",
                    "--summary",
                    "External source treated as untrusted research evidence.",
                    "--risk-flag",
                    "untrusted_content",
                    "--ref",
                    "docs/sejong/SECURITY.md",
                ]
            )
            self.assertEqual(append.returncode, 0, append.stderr)

            check = run_sillok(["check", str(trace)])
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_lethal_trifecta_requires_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "sillok-record.jsonl"
            append = run_sillok(
                [
                    "append",
                    "--trace",
                    str(trace),
                    "--run-id",
                    "run-test",
                    "--active-context-id",
                    "ctx-test",
                    "--surface",
                    "seungjeongwon",
                    "--event-kind",
                    "tool_call",
                    "--summary",
                    "Would combine private data, untrusted content, and an external action.",
                    "--risk-flag",
                    "private_data",
                    "--risk-flag",
                    "untrusted_content",
                    "--risk-flag",
                    "external_action",
                ]
            )
            self.assertNotEqual(append.returncode, 0)
            self.assertIn("lethal trifecta", append.stderr)

    def test_credential_bearing_untrusted_read_is_traceable_without_external_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "sillok-record.jsonl"
            append = run_sillok(
                [
                    "append",
                    "--trace",
                    str(trace),
                    "--run-id",
                    "run-test",
                    "--active-context-id",
                    "ctx-test",
                    "--surface",
                    "sillok",
                    "--event-kind",
                    "security_review",
                    "--summary",
                    "Connected tool output recorded as untrusted credential-bearing read evidence.",
                    "--risk-flag",
                    "credential_access",
                    "--risk-flag",
                    "network_access",
                    "--risk-flag",
                    "untrusted_content",
                    "--ref",
                    "docs/sejong/SECURITY.md#workflow-rules",
                ]
            )
            self.assertEqual(append.returncode, 0, append.stderr)
            check = run_sillok(["check", str(trace)])
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_credential_bearing_lethal_trifecta_still_requires_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "sillok-record.jsonl"
            append = run_sillok(
                [
                    "append",
                    "--trace",
                    str(trace),
                    "--run-id",
                    "run-test",
                    "--active-context-id",
                    "ctx-test",
                    "--surface",
                    "seungjeongwon",
                    "--event-kind",
                    "tool_call",
                    "--summary",
                    "Credential-bearing tool would combine private data, untrusted content, and external action.",
                    "--risk-flag",
                    "private_data",
                    "--risk-flag",
                    "credential_access",
                    "--risk-flag",
                    "untrusted_content",
                    "--risk-flag",
                    "external_action",
                ]
            )
            self.assertNotEqual(append.returncode, 0)
            self.assertIn("lethal trifecta", append.stderr)

    def test_lethal_trifecta_with_human_approval_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "sillok-record.jsonl"
            append = run_sillok(
                [
                    "append",
                    "--trace",
                    str(trace),
                    "--run-id",
                    "run-test",
                    "--active-context-id",
                    "ctx-test",
                    "--surface",
                    "seungjeongwon",
                    "--event-kind",
                    "tool_call",
                    "--summary",
                    "Approved external action with private data and untrusted content.",
                    "--risk-flag",
                    "private_data",
                    "--risk-flag",
                    "untrusted_content",
                    "--risk-flag",
                    "external_action",
                    "--human-approval-ref",
                    "user-approved-2026-05-24",
                ]
            )
            self.assertEqual(append.returncode, 0, append.stderr)
            check = run_sillok(["check", str(trace)])
            self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == "__main__":
    unittest.main()
