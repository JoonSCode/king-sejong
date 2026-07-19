#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from candidate_handoff import ArtifactInput, CandidateHandoffSpec, CommandEvidence, write_candidate_handoff
from codex_ticket_test_support import ticket
from discord_contract_types import ControlContractError


class CandidateHandoffTests(unittest.TestCase):
    def test_writes_immutable_candidate_and_evidence_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: explicit workspace, diff, command, artifact, and producer observations.
            root = Path(tmp)
            artifact = root / "ticket-run-receipt.json"
            artifact.write_text('{"status":"process_completed"}\n', encoding="utf-8")
            spec = CandidateHandoffSpec(
                sejong_home=root / "sejong",
                ticket=replace(ticket(), dry_run=False),
                producer_run_id="producer-run-1",
                workspace=root / "worktree",
                base_commit="a" * 40,
                head_commit="b" * 40,
                dirty_before=False,
                dirty_after=True,
                diff_bytes=b"diff --git a/docs/example.md b/docs/example.md\n",
                commands=(CommandEvidence(("python3", "-m", "unittest"), 0, "artifact://test-log"),),
                artifacts=(ArtifactInput(artifact, "sejong.codex-ticket-run-receipt/v0.1-draft", ("command:test",)),),
                unknowns=("live Discord projection not configured",),
                next_run_constraints=("review candidate hash exactly",),
            )

            # When: Core seals the producer handoff.
            result = write_candidate_handoff(spec)

            # Then: both artifacts bind the candidate and remain evidence-only.
            handoff = json.loads(result.handoff_path.read_text(encoding="utf-8"))
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(handoff["format"], "sejong.codex-candidate-handoff/v0.1-draft")
            self.assertEqual(handoff["ticket_id"], spec.ticket.ticket_id)
            self.assertEqual(handoff["workspace"]["base_commit"], spec.base_commit)
            self.assertEqual(handoff["workspace"]["head_commit"], spec.head_commit)
            self.assertEqual(handoff["producer"]["model"], spec.ticket.model)
            self.assertFalse(handoff["completion_eligible"])
            self.assertEqual(manifest["commands"][0]["exit_code"], 0)
            self.assertEqual(manifest["artifacts"][0]["size_bytes"], artifact.stat().st_size)
            self.assertEqual(len(result.candidate_sha256), 64)
            self.assertEqual(
                handoff["evidence_manifest_sha256"],
                hashlib.sha256(result.manifest_path.read_bytes()).hexdigest(),
            )

            # When/Then: a second writer cannot overwrite the sealed candidate.
            with self.assertRaises(ControlContractError) as raised:
                write_candidate_handoff(spec)
            self.assertEqual(raised.exception.code, "immutable_handoff_exists")

    def test_rejects_unbound_workspace_and_commit_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a handoff whose workspace is relative and base observation is empty.
            root = Path(tmp)
            spec = CandidateHandoffSpec(
                sejong_home=root / "sejong",
                ticket=replace(ticket(), dry_run=False),
                producer_run_id="producer-run-1",
                workspace=Path("relative-worktree"),
                base_commit="",
                head_commit="b" * 40,
                dirty_before=False,
                dirty_after=False,
                diff_bytes=b"",
                commands=(),
                artifacts=(),
                unknowns=(),
                next_run_constraints=(),
            )

            # When/Then: Core refuses a candidate that cannot bind repository state.
            with self.assertRaises(ControlContractError) as raised:
                write_candidate_handoff(spec)
            self.assertEqual(raised.exception.code, "invalid_handoff")

    def test_rejects_candidate_without_command_and_artifact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: valid workspace identity but no producer verification or artifact.
            root = Path(tmp)
            spec = CandidateHandoffSpec(
                sejong_home=root / "sejong",
                ticket=replace(ticket(), dry_run=False),
                producer_run_id="producer-run-1",
                workspace=root / "worktree",
                base_commit="a" * 40,
                head_commit="b" * 40,
                dirty_before=False,
                dirty_after=False,
                diff_bytes=b"",
                commands=(),
                artifacts=(),
                unknowns=(),
                next_run_constraints=(),
            )

            # When/Then: an empty handoff cannot masquerade as a reviewable candidate.
            with self.assertRaises(ControlContractError) as raised:
                write_candidate_handoff(spec)
            self.assertEqual(raised.exception.code, "invalid_evidence")


if __name__ == "__main__":
    unittest.main()
