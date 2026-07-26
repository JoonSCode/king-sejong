#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.11", "typer>=0.16"]
# ///
# ─── How to run ───
# uv run docs/sejong/scripts/test_work_lifecycle.py

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
WORK_LIFECYCLE = SEJONG_ROOT / "scripts" / "work_lifecycle.py"


def event(*, event_id: str, run_id: str, occurred_at: str) -> dict[str, bool | float | str | list[dict[str, str]] | dict[str, bool]]:
    return {
        "format": "sejong.work-event/v0.1-draft",
        "event_id": event_id,
        "occurred_at": occurred_at,
        "run_id": run_id,
        "repo_id": "repo-example",
        "task_class": "implementation",
        "event_type": "user_intervention",
        "epistemic_status": "known",
        "pattern_key": "cleanup.provenance_first",
        "summary": "Cleanup target needed provenance before removal.",
        "response": "Inspect ownership and dry-run before deletion.",
        "outcome": "Unmanaged files were preserved.",
        "source_refs": [
            {
                "ref": f"sillok://{run_id}/{event_id}",
                "sha256": hashlib.sha256(event_id.encode()).hexdigest(),
            }
        ],
        "confidence": 0.98,
        "privacy": {
            "raw_evidence_copied": False,
            "contains_secret": False,
            "contains_private_absolute_path": False,
        },
    }


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORK_LIFECYCLE), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


class WorkLifecycleTests(unittest.TestCase):
    def test_record_event_appends_sanitized_event_with_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "event.json"
            ledger = root / "work-events.jsonl"
            source.write_text(json.dumps(event(event_id="evt-1", run_id="run-1", occurred_at="2026-07-01T00:00:00Z")))

            result = run_cli(["record-event", "--event", str(source), "--ledger", str(ledger)])

            self.assertEqual(result.returncode, 0, result.stderr)
            stored = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(stored["event_id"], "evt-1")
            self.assertEqual(ledger.stat().st_mode & 0o777, 0o600)

    def test_record_event_rejects_raw_transcript_field_without_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "event.json"
            ledger = root / "work-events.jsonl"
            unsafe = event(event_id="evt-1", run_id="run-1", occurred_at="2026-07-01T00:00:00Z")
            unsafe["raw_transcript"] = "full conversation"
            source.write_text(json.dumps(unsafe))

            result = run_cli(["record-event", "--event", str(source), "--ledger", str(ledger)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw_transcript", result.stderr)
            self.assertFalse(ledger.exists())

    def test_record_event_rejects_private_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "event.json"
            unsafe = event(event_id="evt-1", run_id="run-1", occurred_at="2026-07-01T00:00:00Z")
            unsafe["summary"] = "Touched /Users/example/private/notes.txt"
            source.write_text(json.dumps(unsafe))

            result = run_cli(["record-event", "--event", str(source), "--ledger", str(root / "ledger.jsonl")])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("private absolute path", result.stderr)

    def test_derive_candidate_requires_two_independent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "event.json"
            ledger = root / "work-events.jsonl"
            output = root / "lesson-candidate.json"
            source.write_text(json.dumps(event(event_id="evt-1", run_id="run-1", occurred_at="2026-07-01T00:00:00Z")))
            self.assertEqual(run_cli(["record-event", "--event", str(source), "--ledger", str(ledger)]).returncode, 0)

            result = run_cli(
                [
                    "derive-candidate",
                    "--ledger",
                    str(ledger),
                    "--pattern-key",
                    "cleanup.provenance_first",
                    "--output",
                    str(output),
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("two independent runs", result.stderr)
            self.assertFalse(output.exists())

    def test_derive_candidate_is_deterministic_for_repeated_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "work-events.jsonl"
            output_one = root / "candidate-one.json"
            output_two = root / "candidate-two.json"
            for event_id, run_id, occurred_at in (
                ("evt-2", "run-2", "2026-07-02T00:00:00Z"),
                ("evt-1", "run-1", "2026-07-01T00:00:00Z"),
            ):
                source = root / f"{event_id}.json"
                source.write_text(json.dumps(event(event_id=event_id, run_id=run_id, occurred_at=occurred_at)))
                self.assertEqual(run_cli(["record-event", "--event", str(source), "--ledger", str(ledger)]).returncode, 0)

            args = ["--ledger", str(ledger), "--pattern-key", "cleanup.provenance_first"]
            first = run_cli(["derive-candidate", *args, "--output", str(output_one)])
            second = run_cli(["derive-candidate", *args, "--output", str(output_two)])

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            candidate_one = json.loads(output_one.read_text(encoding="utf-8"))
            candidate_two = json.loads(output_two.read_text(encoding="utf-8"))
            self.assertEqual(candidate_one, candidate_two)
            self.assertEqual(candidate_one["independent_run_ids"], ["run-1", "run-2"])
            self.assertEqual(candidate_one["occurrence_count"], 2)
            self.assertEqual(candidate_one["activation_authority"], "none")


if __name__ == "__main__":
    unittest.main()
