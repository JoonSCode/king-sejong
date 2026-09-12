#!/usr/bin/env python3
"""Exercise artifact validation through exact-session source hook calls."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from sejong_paths import repo_identity
from test_session_binding_context import REPO_ROOT, SEJONG_ROOT, run_hook, start_context


class HookArtifactBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hook-artifact-boundary-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.cwd = REPO_ROOT
        self.context_path = start_context(
            self.home, repo_root=REPO_ROOT, run_id="artifact-boundary",
            session_id="bound-session", intent="Inspect this objective.",
        )
        self.context = json.loads(self.context_path.read_text())
        self.context.update(pending_gates=[], task_class="validation_review")
        self.artifact = self.context_path.parent / "continuity-capsule.json"
        self.context["artifact_refs"] = [str(self.artifact)]
        self.context_path.write_text(json.dumps(self.context))
        self.capsule = json.loads((SEJONG_ROOT / "examples/continuity-capsule.example.json").read_text())
        self.capsule.update(
            active_context_id=self.context["active_context_id"],
            run_id=self.context["run_id"], repo_root=str(REPO_ROOT),
            task_class=self.context["task_class"], next_action="BOUND NEXT ACTION",
        )

    def invoke(self, event: str, *, session: str = "bound-session") -> dict:
        return run_hook(event, {
            "hook_event_name": event, "session_id": session, "turn_id": "opaque",
            "cwd": str(self.cwd), "prompt": "continue", "source": "compact", "trigger": "auto",
        }, self.home)

    def assert_rejected(self) -> None:
        for event in ("UserPromptSubmit", "SessionStart"):
            with self.subTest(event=event):
                result = self.invoke(event)
                self.assertNotIn("BOUND NEXT ACTION", json.dumps(result))
        self.assertEqual(self.invoke("Stop").get("decision"), "block")
        self.assertIs(self.invoke("PreCompact").get("continue"), False)

    def test_valid_capsule_and_unbound_session_control(self) -> None:
        self.artifact.write_text(json.dumps(self.capsule))
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertIn("BOUND NEXT ACTION", json.dumps(self.invoke(event)))
            self.assertEqual(self.invoke(event, session="unbound"), {})
        self.assertEqual(self.invoke("Stop"), {})
        self.assertEqual(self.invoke("PreCompact"), {})

    def test_foreign_capsule_identity_run_repo_and_task_are_rejected_individually(self) -> None:
        for field, value in (
            ("active_context_id", "foreign-context"), ("run_id", "foreign-run"),
            ("repo_root", str(self.home / "foreign-repository")), ("task_class", "foreign-task"),
        ):
            with self.subTest(field=field):
                self.artifact.write_text(json.dumps({**self.capsule, field: value}))
                self.assert_rejected()

    def test_legacy_context_without_task_class_keeps_matching_capsule(self) -> None:
        del self.context["task_class"]
        self.context_path.write_text(json.dumps(self.context))
        self.artifact.write_text(json.dumps(self.capsule))
        self.assertIn("BOUND NEXT ACTION", json.dumps(self.invoke("SessionStart")))

    def test_objective_identifier_is_not_compared_to_capsule_prose(self) -> None:
        self.context["objective_id"] = "objective-identifier"
        self.context["last_user_intent"] = "What is the current status?"
        self.context_path.write_text(json.dumps(self.context))
        self.artifact.write_text(json.dumps(self.capsule))
        self.assertIn("BOUND NEXT ACTION", json.dumps(self.invoke("SessionStart")))

    def test_worktree_and_explicit_additional_repo_match_but_nested_repo_does_not(self) -> None:
        repository = self.home / "repository"
        repository.mkdir()
        for command in (
            ["git", "init", str(repository)],
            ["git", "-C", str(repository), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "fixture"],
            ["git", "-C", str(repository), "worktree", "add", "--detach", str(self.home / "worktree")],
        ):
            subprocess.run(command, check=True, capture_output=True, text=True)
        self.context["repo_identities"].append(repo_identity(repository))
        self.context_path.write_text(json.dumps(self.context))
        self.cwd = repository
        for capsule_root in (repository, self.home / "worktree"):
            self.artifact.write_text(json.dumps({**self.capsule, "repo_root": str(capsule_root)}))
            self.assertIn("BOUND NEXT ACTION", json.dumps(self.invoke("SessionStart")))
        nested = repository / "nested"
        subprocess.run(["git", "init", str(nested)], check=True, capture_output=True, text=True)
        self.artifact.write_text(json.dumps({**self.capsule, "repo_root": str(nested)}))
        self.assert_rejected()

    def test_capsule_scalar_fields_are_validated_before_projection(self) -> None:
        for field in ("repo_root", "active_context_id", "current_surface", "objective", "task_class"):
            with self.subTest(field=field):
                self.artifact.write_text(json.dumps({**self.capsule, field: []}))
                self.assert_rejected()

    def test_malformed_known_artifact_roots_block_without_tracebacks(self) -> None:
        for name in ("continuity-capsule.json", "ambiguity-register.json", "seungjeongwon-run.json"):
            self.artifact = self.context_path.parent / name
            self.context["artifact_refs"] = [str(self.artifact)]
            self.context_path.write_text(json.dumps(self.context))
            for value in ([], None, "text", 7, {}):
                with self.subTest(name=name, value=value):
                    self.artifact.write_text(json.dumps(value))
                    self.assert_rejected()

    def test_untyped_json_evidence_array_does_not_crash_or_create_a_gate(self) -> None:
        self.artifact = self.context_path.parent / "measurements.json"
        self.artifact.write_text('[1, 2]')
        self.context["artifact_refs"] = [str(self.artifact)]
        self.context_path.write_text(json.dumps(self.context))
        self.invoke("UserPromptSubmit")
        self.assertEqual(self.invoke("Stop"), {})
        self.assertEqual(self.invoke("PreCompact"), {})


if __name__ == "__main__":
    unittest.main()
