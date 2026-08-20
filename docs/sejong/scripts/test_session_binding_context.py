#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeAlias
from unittest import mock


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
sys.path.insert(0, str(CONTEXT_SCRIPT.parent))
import sejong_context as context_module  # noqa: E402
import sejong_session_binding as binding_module  # noqa: E402


def run_context(args: list[str], sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "SEJONG_HOME": str(sejong_home),
            "SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS": "0.1",
        },
    )


def run_hook(
    event_name: str,
    payload: dict[str, JsonValue],
    sejong_home: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> dict[str, JsonValue]:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home), **(extra_env or {})},
    )
    if result.returncode != 0:
        raise AssertionError(f"hook failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout or "{}")


def start_context(
    sejong_home: Path,
    *,
    repo_root: Path,
    run_id: str,
    session_id: str,
    intent: str,
    additional_repo_roots: tuple[Path, ...] = (),
) -> Path:
    additional_repo_args = [
        item
        for path in additional_repo_roots
        for item in ("--additional-repo-root", str(path))
    ]
    result = run_context(
        [
            "start",
            "--repo-root",
            str(repo_root),
            *additional_repo_args,
            "--run-id",
            run_id,
            "--session-id",
            session_id,
            "--current-surface",
            "uigwe",
            "--pending-gate",
            "verification",
            "--last-user-intent",
            intent,
        ],
        sejong_home,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    run_line = next(line for line in result.stdout.splitlines() if line.startswith("run_context="))
    return Path(run_line.removeprefix("run_context="))


def additional_context(output: dict[str, JsonValue]) -> str:
    hook_output = output.get("hookSpecificOutput")
    if not isinstance(hook_output, dict):
        return ""
    value = hook_output.get("additionalContext")
    return value if isinstance(value, str) else ""


def prompt_payload(session_id: str, turn_id: str, cwd: Path = REPO_ROOT) -> dict[str, JsonValue]:
    return {
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "turn_id": turn_id,
        "cwd": str(cwd),
        "prompt": "continue",
    }


def session_start_payload(session_id: str, turn_id: str, cwd: Path = REPO_ROOT) -> dict[str, JsonValue]:
    return {
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "turn_id": turn_id,
        "cwd": str(cwd),
        "source": "compact",
    }


class SessionBindingContextTests(unittest.TestCase):
    def test_epoch_changes_only_when_binding_target_or_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="stable-epoch",
                session_id="session-a",
                intent="stable epoch",
            )
            same = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )
            first_unbind = run_context(
                ["unbind", "--session-id", "session-a", "--expect-revision", "2"],
                sejong_home,
            )
            repeat_unbind = run_context(
                ["unbind", "--session-id", "session-a", "--expect-revision", "3"],
                sejong_home,
            )
            bindings = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (sejong_home / "state" / "session-bindings").glob("*.json")
            ]
            binding = next(item for item in bindings if item.get("session_id") == "session-a")

        self.assertEqual(same.returncode, 0, same.stderr)
        self.assertIn("binding_epoch=1", same.stdout)
        self.assertEqual(first_unbind.returncode, 0, first_unbind.stderr)
        self.assertIn("binding_epoch=2", first_unbind.stdout)
        self.assertEqual(repeat_unbind.returncode, 0, repeat_unbind.stderr)
        self.assertEqual(binding["binding_epoch"], 2)
        self.assertEqual(binding["revision"], 4)

    def test_stale_close_does_not_close_or_unbind_current_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="stale-close",
                session_id="session-a",
                intent="must remain active",
            )
            closed = run_context(
                ["close", "--session-id", "session-a", "--expect-revision", "0"],
                sejong_home,
            )
            durable = json.loads(context_path.read_text(encoding="utf-8"))
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-after-stale-close"), sejong_home)

        self.assertNotEqual(closed.returncode, 0)
        self.assertIn("binding revision conflict", closed.stdout + closed.stderr)
        self.assertEqual(durable["context_status"], "active")
        self.assertIn("active_context_id=ctx-stale-close", additional_context(output))

    def test_close_rejects_context_that_is_not_the_sessions_bound_target(self) -> None:
        # Given: sessions A and B own different foreground Contexts.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_a = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="close-target-a",
                session_id="session-a",
                intent="session A target",
            )
            context_b = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="close-target-b",
                session_id="session-b",
                intent="session B target",
            )

            # When: a caller asks to close B's Context using A's binding revision.
            closed = run_context(
                [
                    "close",
                    "--context",
                    str(context_b),
                    "--session-id",
                    "session-a",
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )
            prompt_a = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-after-close-mismatch"),
                sejong_home,
            )
            durable_a = json.loads(context_a.read_text(encoding="utf-8"))
            durable_b = json.loads(context_b.read_text(encoding="utf-8"))

        # Then: neither the session binding nor either durable Context changes target or lifecycle.
        self.assertNotEqual(closed.returncode, 0)
        self.assertIn("does not reference requested Context", closed.stdout + closed.stderr)
        self.assertIn("active_context_id=ctx-close-target-a", additional_context(prompt_a))
        self.assertEqual(durable_a["context_status"], "active")
        self.assertEqual(durable_b["context_status"], "active")

    def test_explicit_resume_rejects_empty_session_identity(self) -> None:
        # Given: a valid durable Context exists for another exact session.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="empty-session-resume",
                session_id="session-a",
                intent="empty session ids have no authority",
            )

            # When: explicit resume supplies an empty host session identity.
            resumed = run_context(
                [
                    "resume",
                    "--context",
                    str(context_path),
                    "--session-id",
                    "",
                    "--expect-revision",
                    "0",
                ],
                sejong_home,
            )
            binding_count = len(list((sejong_home / "state" / "session-bindings").glob("*.json")))

        # Then: no anonymous binding is created.
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("non-empty session id", resumed.stdout + resumed.stderr)
        self.assertEqual(binding_count, 1)

    def test_malformed_binding_fails_closed_for_protected_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="malformed-binding",
                session_id="session-a",
                intent="protected work",
            )
            binding_path = next((sejong_home / "state" / "session-bindings").glob("*.json"))
            binding_path.write_text("{not-json", encoding="utf-8")

            output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-a",
                    "turn_id": "turn-protected",
                    "cwd": str(REPO_ROOT),
                    "tool_name": "apply_patch",
                    "tool_input": {"patch": "docs/sejong/HOOKS.md"},
                },
                sejong_home,
            )

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("session binding is invalid", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_binding_lock_contention_is_quiet_for_prompt_and_closed_for_protected_work(self) -> None:
        # Given: the exact session binding is valid but another live process owns its lock.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="contended-binding",
                session_id="session-a",
                intent="binding contention must not crash hooks",
            )
            key = hashlib.sha256(b"codex\0session-a").hexdigest()
            lock_path = sejong_home / "state" / "locks" / f"session-binding-{key}.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            lock_path.write_text(
                json.dumps(
                    {
                        "format": "sejong.runtime-lock/v0.1-draft",
                        "lock_name": f"session-binding-{key}",
                        "lock_class": "session-binding",
                        "owner_session_id": "live-other-owner",
                        "owner_process_id": os.getpid(),
                        "owner_device_id": "test-device",
                        "operation": "hold for deterministic contention",
                        "token": "held-token",
                        "created_at": timestamp,
                        "heartbeat_at": timestamp,
                    }
                ),
                encoding="utf-8",
            )
            timeout_env = {"SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS": "0.05"}

            # When: ordinary and protected hooks resolve the contended binding.
            prompt = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-contended-prompt"),
                sejong_home,
                extra_env=timeout_env,
            )
            protected = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-a",
                    "turn_id": "turn-contended-protected",
                    "cwd": str(REPO_ROOT),
                    "tool_name": "apply_patch",
                    "tool_input": {"patch": "*** Update File: docs/sejong/HOOKS.md"},
                },
                sejong_home,
                extra_env=timeout_env,
            )

        # Then: contention is a bounded binding error rather than a hook-process crash.
        self.assertEqual(prompt, {})
        self.assertEqual(protected["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("session binding is invalid", protected["hookSpecificOutput"]["permissionDecisionReason"])

    def test_schema_incomplete_binding_cannot_inject_and_fails_closed_for_protected_work(self) -> None:
        # Given: the binding parses and names the correct session but omits a required record field.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="incomplete-binding",
                session_id="session-a",
                intent="incomplete binding must have no authority",
            )
            binding_path = next((sejong_home / "state" / "session-bindings").glob("*.json"))
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            binding.pop("updated_at")
            binding_path.write_text(json.dumps(binding), encoding="utf-8")

            # When: ordinary and protected hooks load that structurally incomplete binding.
            prompt = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-incomplete-prompt"),
                sejong_home,
            )
            protected = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-a",
                    "turn_id": "turn-incomplete-protected",
                    "cwd": str(REPO_ROOT),
                    "tool_name": "apply_patch",
                    "tool_input": {"patch": "*** Update File: docs/sejong/HOOKS.md"},
                },
                sejong_home,
            )

        # Then: schema-incomplete runtime state is non-authoritative.
        self.assertEqual(prompt, {})
        self.assertEqual(protected["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("session binding is invalid", protected["hookSpecificOutput"]["permissionDecisionReason"])

    def test_malformed_bound_context_cannot_inject_or_create_another_binding(self) -> None:
        # Given: the binding is valid but its durable Context loses a required field.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="malformed-context",
                session_id="session-a",
                intent="must never inject after corruption",
            )
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context.pop("last_user_intent")
            context["protected_paths"] = ["docs/sejong/"]
            context_path.write_text(json.dumps(context), encoding="utf-8")

            # When: the bound session submits and writes, and a second session explicitly resumes it.
            prompt_output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-malformed-context"),
                sejong_home,
            )
            protected_output = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-a",
                    "turn_id": "turn-malformed-write",
                    "cwd": str(REPO_ROOT),
                    "tool_name": "apply_patch",
                    "tool_input": {"patch": "*** Update File: docs/sejong/HOOKS.md"},
                },
                sejong_home,
            )
            resumed = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-b",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "0",
                ],
                sejong_home,
            )

        # Then: ordinary injection is quiet, protected work is denied, and no new binding is created.
        self.assertEqual(prompt_output, {})
        self.assertEqual(protected_output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(
            "session binding is invalid",
            protected_output["hookSpecificOutput"]["permissionDecisionReason"],
        )
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("invalid durable context", resumed.stdout + resumed.stderr)

    def test_wrong_typed_required_context_field_cannot_inject_or_resume(self) -> None:
        # Given: an otherwise complete durable Context has a schema-invalid required string field.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="wrong-typed-context",
                session_id="session-a",
                intent="must never inject after type corruption",
            )
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["repo_root"] = 42
            context_path.write_text(json.dumps(context), encoding="utf-8")

            # When: the bound session submits and a second session explicitly resumes it.
            prompt_output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-wrong-typed-context"),
                sejong_home,
            )
            resumed = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-b",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "0",
                ],
                sejong_home,
            )

        # Then: runtime validation enforces the same non-empty string boundary as the schema.
        self.assertEqual(prompt_output, {})
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("repo_root must be a non-empty string", resumed.stdout + resumed.stderr)

    def test_internal_session_mismatch_never_injects_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="session-mismatch",
                session_id="session-a",
                intent="must stay private to session A",
            )
            binding_path = next((sejong_home / "state" / "session-bindings").glob("*.json"))
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            binding["session_id"] = "session-b"
            binding_path.write_text(json.dumps(binding), encoding="utf-8")

            prompt = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-mismatch"), sejong_home)
            protected = run_hook(
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-a",
                    "turn_id": "turn-mismatch-protected",
                    "cwd": str(REPO_ROOT),
                    "tool_name": "apply_patch",
                    "tool_input": {"patch": "docs/sejong/HOOKS.md"},
                },
                sejong_home,
            )

        self.assertEqual(prompt, {})
        self.assertEqual(protected["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_second_start_for_same_session_requires_explicit_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="first-start",
                session_id="session-a",
                intent="first",
            )
            second = run_context(
                [
                    "start",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "second-start",
                    "--session-id",
                    "session-a",
                    "--last-user-intent",
                    "second",
                ],
                sejong_home,
            )
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-after-race"), sejong_home)

        self.assertNotEqual(second.returncode, 0)
        self.assertIn("binding revision conflict", second.stdout + second.stderr)
        self.assertIn("active_context_id=ctx-first-start", additional_context(output))

    def test_same_repo_two_sessions_inject_only_each_foreground_context(self) -> None:
        # Given: two Codex sessions own different contexts in the same Git repository.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="same-repo-a",
                session_id="session-a",
                intent="session A intent",
            )
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="same-repo-b",
                session_id="session-b",
                intent="session B intent",
            )

            # When: each session submits a prompt with its own host identity.
            output_a = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-a2"), sejong_home)
            output_b = run_hook("UserPromptSubmit", prompt_payload("session-b", "turn-b2"), sejong_home)

        # Then: each hook projection contains only the context bound to that session.
        context_a = additional_context(output_a)
        context_b = additional_context(output_b)
        self.assertIn("active_context_id=ctx-same-repo-a", context_a)
        self.assertNotIn("ctx-same-repo-b", context_a)
        self.assertIn("active_context_id=ctx-same-repo-b", context_b)
        self.assertNotIn("ctx-same-repo-a", context_b)

    def test_unbound_new_session_does_not_inject_latest_repo_context(self) -> None:
        # Given: a repository has a recent context bound to a different session.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="existing-run",
                session_id="session-existing",
                intent="existing session intent",
            )

            # When: a new unbound session submits a prompt from the same repository.
            output = run_hook("UserPromptSubmit", prompt_payload("session-new", "turn-new1"), sejong_home)

        # Then: repository recency does not grant context injection authority.
        context = additional_context(output)
        self.assertNotIn("ctx-existing-run", context)
        self.assertNotIn("existing session intent", context)

    def test_compact_resume_restores_exact_context_for_same_session(self) -> None:
        # Given: session A was bound before a newer same-repository session B context appeared.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="compact-a",
                session_id="session-a",
                intent="compact A intent",
            )
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="compact-b",
                session_id="session-b",
                intent="compact B intent",
            )

            # When: Codex restarts session A after compaction.
            output = run_hook("SessionStart", session_start_payload("session-a", "turn-a-compact"), sejong_home)

        # Then: the exact session A context is restored, not the newest repository context.
        context = additional_context(output)
        self.assertIn("active_context_id=ctx-compact-a", context)
        self.assertNotIn("ctx-compact-b", context)

    def test_explicit_switch_pauses_previous_binding_before_replace(self) -> None:
        # Given: session A and session B each have a foreground context.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_a = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="switch-a",
                session_id="session-a",
                intent="switch A intent",
            )
            context_b = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="switch-b",
                session_id="session-b",
                intent="switch B intent",
            )

            # When: session A explicitly switches to context B using its current generation.
            switched = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-switch",
                    "--context",
                    str(context_b),
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-switch-next"), sejong_home)
            history_paths = list((sejong_home / "state" / "session-bindings" / "history").glob("**/*.json"))
            history = [json.loads(path.read_text(encoding="utf-8")) for path in history_paths]

        # Then: replacement succeeds, old context is paused in history, and B is foreground.
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertIn("active_context_id=ctx-switch-b", additional_context(output))
        self.assertTrue(
            any(
                item.get("status") == "paused" and item.get("context_ref") == str(context_a.resolve())
                for item in history
            )
        )

    def test_switch_commit_survives_history_and_repo_index_write_failures(self) -> None:
        # Given: session A can switch to B, but both reconstructable derived-state destinations are unavailable.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="derived-a",
                session_id="session-a",
                intent="derived A intent",
            )
            context_b = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="derived-b",
                session_id="session-b",
                intent="derived B intent",
            )
            history_root = sejong_home / "state" / "session-bindings" / "history"
            history_root.write_text("not-a-directory", encoding="utf-8")
            repo_index_root = sejong_home / "state" / "repo-index"
            for index_path in repo_index_root.glob("*"):
                index_path.unlink()
            repo_index_root.rmdir()
            repo_index_root.write_text("not-a-directory", encoding="utf-8")

            # When: the atomic binding replacement commits before either derived update.
            switched = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-derived-switch",
                    "--context",
                    str(context_b),
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )
            output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-after-derived-failure"),
                sejong_home,
            )

        # Then: the authority commit remains successful and reconstructable failures are warnings only.
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertIn("binding history update failed", switched.stderr)
        self.assertIn("repo index update failed", switched.stderr)
        self.assertIn("active_context_id=ctx-derived-b", additional_context(output))
        self.assertNotIn("ctx-derived-a", additional_context(output))

    def test_nested_git_repo_does_not_match_parent_repo_context(self) -> None:
        # Given: a context is bound to a parent Git repository and cwd is a nested Git repository.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong-home"
            parent_repo = root / "parent"
            nested_repo = parent_repo / "nested"
            parent_repo.mkdir()
            nested_repo.mkdir()
            subprocess.run(["git", "init", "-q", str(parent_repo)], check=True)
            subprocess.run(["git", "init", "-q", str(nested_repo)], check=True)
            start_context(
                sejong_home,
                repo_root=parent_repo,
                run_id="parent-run",
                session_id="session-a",
                intent="parent repository intent",
            )

            # When: the bound session submits from the nested repository.
            output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-nested", nested_repo),
                sejong_home,
            )

        # Then: parent path containment does not authorize nested-repository injection.
        context = additional_context(output)
        self.assertNotIn("ctx-parent-run", context)
        self.assertNotIn("parent repository intent", context)

    def test_broad_non_git_parent_does_not_authorize_sibling_git_repo(self) -> None:
        # Given: a legacy-shaped broad parent path contains a distinct sibling Git repository.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong-home"
            broad_parent = root / "workspace"
            sibling_repo = broad_parent / "sibling-repo"
            sibling_repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(sibling_repo)], check=True)
            start_context(
                sejong_home,
                repo_root=broad_parent,
                run_id="broad-parent",
                session_id="session-a",
                intent="broad parent intent",
            )

            # When: the bound session submits from the sibling Git repository.
            output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-sibling", sibling_repo),
                sejong_home,
            )

        # Then: path containment cannot widen the exact repository identity boundary.
        self.assertEqual(output, {})

    def test_explicit_multi_repo_context_authorizes_only_declared_repo_identities(self) -> None:
        # Given: a Context explicitly declares two repositories and omits a third sibling.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong-home"
            repo_a = root / "repo-a"
            repo_b = root / "repo-b"
            repo_c = root / "repo-c"
            for repo in (repo_a, repo_b, repo_c):
                repo.mkdir()
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
            start_context(
                sejong_home,
                repo_root=repo_a,
                additional_repo_roots=(repo_b,),
                run_id="multi-repo",
                session_id="session-a",
                intent="exact multi repo intent",
            )

            # When: the same bound session submits once from each repository.
            output_a = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-a", repo_a), sejong_home)
            output_b = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-b", repo_b), sejong_home)
            output_c = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-c", repo_c), sejong_home)

        # Then: only the exact declared repository identities receive the Context.
        self.assertIn("active_context_id=ctx-multi-repo", additional_context(output_a))
        self.assertIn("active_context_id=ctx-multi-repo", additional_context(output_b))
        self.assertEqual(output_c, {})

    def test_git_common_dir_matches_linked_worktree_and_symlinked_repo_path(self) -> None:
        # Given: one Git repository is reached through its main worktree, a linked worktree, and a symlink.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sejong_home = root / "sejong-home"
            main_repo = root / "main-repo"
            linked_worktree = root / "linked-worktree"
            repo_symlink = root / "repo-symlink"
            main_repo.mkdir()
            subprocess.run(["git", "init", "-q", str(main_repo)], check=True)
            subprocess.run(["git", "-C", str(main_repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(main_repo), "config", "user.name", "King Sejong Test"], check=True)
            (main_repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(main_repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(main_repo), "commit", "-q", "-m", "fixture"], check=True)
            subprocess.run(
                ["git", "-C", str(main_repo), "worktree", "add", "-q", "-b", "linked-test", str(linked_worktree)],
                check=True,
            )
            repo_symlink.symlink_to(main_repo, target_is_directory=True)
            start_context(
                sejong_home,
                repo_root=main_repo,
                run_id="common-dir",
                session_id="session-a",
                intent="common dir intent",
            )

            # When: hook payloads arrive from the linked worktree and symlinked path.
            linked_output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-linked", linked_worktree),
                sejong_home,
            )
            symlink_output = run_hook(
                "UserPromptSubmit",
                prompt_payload("session-a", "turn-symlink", repo_symlink),
                sejong_home,
            )

        # Then: both resolve to the same Git common-directory identity as the main worktree.
        self.assertIn("active_context_id=ctx-common-dir", additional_context(linked_output))
        self.assertIn("active_context_id=ctx-common-dir", additional_context(symlink_output))

    def test_repo_identity_digest_preserves_case_distinct_canonical_paths(self) -> None:
        # Given: two canonical paths differ only by case, as case-sensitive APFS permits.
        scripts_root = str(SEJONG_ROOT / "scripts")
        if scripts_root not in sys.path:
            sys.path.insert(0, scripts_root)
        from sejong_paths import identity_path_digest

        upper = Path("/Volumes/CaseSensitive/Repo/.git")
        lower = Path("/Volumes/CaseSensitive/repo/.git")

        # When: persisted repository identity digests are computed.
        upper_digest = identity_path_digest(upper)
        lower_digest = identity_path_digest(lower)

        # Then: Darwin platform defaults must not collapse distinct filesystem entries.
        self.assertNotEqual(upper_digest, lower_digest)

    def test_completed_context_is_not_injected_by_existing_binding(self) -> None:
        # Given: a session-bound durable context has completed.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="completed-run",
                session_id="session-a",
                intent="completed intent",
            )
            context_data = json.loads(context_path.read_text(encoding="utf-8"))
            context_data["context_status"] = "completed"
            context_path.write_text(json.dumps(context_data), encoding="utf-8")

            # When: the same session submits another prompt.
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-after-complete"), sejong_home)

        # Then: lifecycle completion removes automatic injection authority.
        context = additional_context(output)
        self.assertNotIn("ctx-completed-run", context)
        self.assertNotIn("completed intent", context)

    def test_legacy_pointer_migration_preserves_file_without_binding_new_session(self) -> None:
        # Given: the old global active pointer contains a broad stale context.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_bytes = json.dumps(
                {
                    "format": "king-sejong.context/v0.1-draft",
                    "active_context_id": "ctx-legacy-magnet",
                    "repo_id": "legacy",
                    "repo_root": str(REPO_ROOT.parent),
                    "run_id": "legacy-run",
                    "session_id": "legacy-session",
                    "route_id": "legacy-route",
                    "current_surface": "sejong",
                    "route_sequence": ["sejong"],
                    "required_route_sequence": [],
                    "last_user_intent": "old Magnet context",
                    "pending_gates": ["verification"],
                    "protected_paths": [],
                    "allowed_direct_change_types": [],
                    "evidence_refs": [],
                    "artifact_refs": [],
                    "team_run_refs": [],
                    "subagent_refs": [],
                    "exit_conditions": ["host_conversation_ends"],
                    "last_updated_at": "2026-07-16T14:12:40Z",
                },
                sort_keys=True,
            ).encode()
            legacy_path.write_bytes(legacy_bytes)

            # When: legacy state is migrated and a new unbound session starts.
            migrated = run_context(["migrate-legacy"], sejong_home)
            output = run_hook("SessionStart", session_start_payload("session-new", "turn-new"), sejong_home)
            preserved_bytes = legacy_path.read_bytes()
            migration_receipt = json.loads(
                (sejong_home / "state" / "legacy-active-context-migration.json").read_text(encoding="utf-8")
            )

        # Then: original bytes remain, migration is recorded, and no legacy context is injected.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertEqual(preserved_bytes, legacy_bytes)
        self.assertTrue(migration_receipt["context_materialized"])
        self.assertTrue(migration_receipt["repo_index_updated"])
        self.assertFalse(migration_receipt["automatic_injection_authority"])
        context = additional_context(output)
        self.assertNotIn("ctx-legacy-magnet", context)
        self.assertNotIn("old Magnet context", context)

    def test_legacy_materialization_cannot_replace_competing_context_creator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy.update(
                {
                    "active_context_id": "ctx-legacy-race",
                    "repo_id": "legacy-race",
                    "run_id": "legacy-race",
                    "repo_root": str(REPO_ROOT),
                    "session_id": "legacy-session",
                }
            )
            legacy.pop("context_revision", None)
            legacy_bytes = (json.dumps(legacy, sort_keys=True) + "\n").encode()
            legacy_path.write_bytes(legacy_bytes)

            def create_competing_context(_candidate: Path, materialized: dict[str, object]) -> None:
                competing = dict(materialized)
                competing["active_context_id"] = "ctx-competing-winner"
                context_module.save_context(
                    competing,
                    expected_context_revision=0,
                    sejong_home=sejong_home,
                    operation="legacy migration race winner",
                )

            with mock.patch.dict(os.environ, {"SEJONG_HOME": str(sejong_home)}):
                receipt_path = binding_module.migrate_legacy_pointer(
                    sejong_home,
                    before_materialize=create_competing_context,
                )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            candidate = sejong_home / "runs/legacy-race/legacy-race/king-sejong-context.json"
            persisted = json.loads(candidate.read_text(encoding="utf-8"))

            self.assertEqual(legacy_path.read_bytes(), legacy_bytes)
            self.assertFalse(receipt["context_materialized"])
            self.assertIn("context identity conflict", receipt["context_materialization_error"])
            self.assertEqual(persisted["active_context_id"], "ctx-competing-winner")
            self.assertEqual(persisted["context_revision"], 1)

    def test_legacy_pointer_migration_rejects_path_traversal_components(self) -> None:
        # Given: persisted legacy metadata tries to escape the durable runs directory.
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            sejong_home = temp_root / "sejong-root"
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_bytes = json.dumps(
                {
                    "active_context_id": "ctx-legacy-traversal",
                    "repo_id": "../..",
                    "repo_root": str(REPO_ROOT),
                    "run_id": "escaped-context",
                },
                sort_keys=True,
            ).encode()
            legacy_path.write_bytes(legacy_bytes)
            escaped_context = temp_root / "escaped-context" / "king-sejong-context.json"

            # When: the non-authoritative legacy record is migrated.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt = json.loads(
                (sejong_home / "state" / "legacy-active-context-migration.json").read_text(encoding="utf-8")
            )
            escaped_context_exists = escaped_context.exists()

        # Then: bytes and receipt survive, but unsafe metadata never becomes a write target.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertFalse(escaped_context_exists)
        self.assertIsNone(receipt["context_ref"])
        self.assertTrue(receipt["legacy_bytes_preserved"])

    def test_legacy_pointer_migration_preserves_malformed_metadata_without_deriving_state(self) -> None:
        # Given: the legacy record is valid JSON but its authority-bearing metadata has invalid types.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy_bytes = json.dumps(
                {
                    "format": "king-sejong.context/v0.1-draft",
                    "active_context_id": ["ctx-not-a-string"],
                    "repo_id": "legacy-safe-name",
                    "repo_root": str(REPO_ROOT),
                    "repo_identities": 7,
                    "run_id": "legacy-malformed",
                    "last_updated_at": "2026-07-16T14:12:40Z",
                },
                sort_keys=True,
            ).encode()
            legacy_path.write_bytes(legacy_bytes)
            derived_context = (
                sejong_home
                / "runs"
                / "legacy-safe-name"
                / "legacy-malformed"
                / "king-sejong-context.json"
            )

            # When: migration processes the malformed but preservable legacy record.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt_path = sejong_home / "state" / "legacy-active-context-migration.json"
            receipt_exists = receipt_path.exists()
            receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_exists else {}
            preserved_bytes = legacy_path.read_bytes()
            derived_context_exists = derived_context.exists()

        # Then: migration succeeds without granting authority or materializing malformed derived state.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertTrue(receipt_exists)
        self.assertEqual(preserved_bytes, legacy_bytes)
        self.assertFalse(derived_context_exists)
        self.assertIsNone(receipt["active_context_id"])
        self.assertIsNone(receipt["context_ref"])
        self.assertFalse(receipt["automatic_injection_authority"])

    def test_legacy_pointer_migration_receipt_survives_repo_index_write_failure(self) -> None:
        # Given: a valid legacy Context can be preserved, but reconstructable Repo Index storage is unavailable.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy["repo_id"] = "legacy-index-failure"
            legacy["run_id"] = "legacy-index-failure"
            legacy_bytes = (json.dumps(legacy, sort_keys=True) + "\n").encode()
            legacy_path.write_bytes(legacy_bytes)
            (sejong_home / "state" / "repo-index").write_text("not-a-directory", encoding="utf-8")

            # When: migration reaches the non-authoritative index update.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt_path = sejong_home / "state" / "legacy-active-context-migration.json"
            receipt_exists = receipt_path.exists()
            receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_exists else {}
            preserved_bytes = legacy_path.read_bytes()

        # Then: derived-index failure is recorded but cannot erase or block the migration receipt.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertTrue(receipt_exists)
        self.assertEqual(preserved_bytes, legacy_bytes)
        self.assertIsNotNone(receipt["context_ref"])
        self.assertFalse(receipt["repo_index_updated"])
        self.assertFalse(receipt["automatic_injection_authority"])

    def test_legacy_pointer_migration_receipt_survives_context_materialization_failure(self) -> None:
        # Given: the legacy record is usable, but the durable runs destination cannot be created.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy["repo_id"] = "legacy-context-failure"
            legacy["run_id"] = "legacy-context-failure"
            legacy_bytes = (json.dumps(legacy, sort_keys=True) + "\n").encode()
            legacy_path.write_bytes(legacy_bytes)
            (sejong_home / "runs").write_text("not-a-directory", encoding="utf-8")

            # When: migration cannot materialize its optional durable copy.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt_path = sejong_home / "state" / "legacy-active-context-migration.json"
            receipt_exists = receipt_path.exists()
            receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_exists else {}
            preserved_bytes = legacy_path.read_bytes()

        # Then: the original and receipt survive without claiming derived Context success or authority.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertTrue(receipt_exists)
        self.assertEqual(preserved_bytes, legacy_bytes)
        self.assertIsNone(receipt["context_ref"])
        self.assertFalse(receipt["context_materialized"])
        self.assertFalse(receipt["repo_index_updated"])
        self.assertFalse(receipt["automatic_injection_authority"])

    def test_legacy_pointer_migration_rejects_symlink_escape_from_runs_root(self) -> None:
        # Given: safe-looking legacy ids resolve through a runs child symlink to an outside directory.
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            sejong_home = temp_root / "sejong-home"
            outside = temp_root / "outside"
            runs_root = sejong_home / "runs"
            legacy_path = sejong_home / "state" / "active-context.json"
            outside.mkdir()
            runs_root.mkdir(parents=True)
            legacy_path.parent.mkdir(parents=True)
            (runs_root / "legacy-symlink").symlink_to(outside, target_is_directory=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy["repo_id"] = "legacy-symlink"
            legacy["run_id"] = "escaped-run"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            escaped_context = outside / "escaped-run" / "king-sejong-context.json"

            # When: migration resolves the candidate destination.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt = json.loads(
                (sejong_home / "state" / "legacy-active-context-migration.json").read_text(encoding="utf-8")
            )
            escaped_context_exists = escaped_context.exists()

        # Then: the symlink cannot widen the configured runs-root boundary.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertFalse(escaped_context_exists)
        self.assertIsNone(receipt["context_ref"])
        self.assertFalse(receipt["context_materialized"])
        self.assertFalse(receipt["repo_index_updated"])

    def test_legacy_pointer_migration_does_not_link_conflicting_existing_context(self) -> None:
        # Given: the derived run path already contains a different durable Context identity.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy["active_context_id"] = "ctx-legacy-expected"
            legacy["repo_id"] = "legacy-conflict"
            legacy["run_id"] = "legacy-conflict"
            legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
            candidate = (
                sejong_home
                / "runs"
                / "legacy-conflict"
                / "legacy-conflict"
                / "king-sejong-context.json"
            )
            conflicting = dict(legacy)
            conflicting["active_context_id"] = "ctx-existing-different"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(conflicting), encoding="utf-8")

            # When: migration encounters the occupied candidate path.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt = json.loads(
                (sejong_home / "state" / "legacy-active-context-migration.json").read_text(encoding="utf-8")
            )
            preserved_candidate = json.loads(candidate.read_text(encoding="utf-8"))

        # Then: the existing file is preserved but never indexed or claimed as the migrated Context.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertEqual(preserved_candidate["active_context_id"], "ctx-existing-different")
        self.assertIsNone(receipt["context_ref"])
        self.assertFalse(receipt["context_materialized"])
        self.assertFalse(receipt["repo_index_updated"])

    def test_legacy_pointer_migration_does_not_materialize_schema_invalid_context(self) -> None:
        # Given: legacy metadata is path-safe but the record is not a valid durable Context.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            legacy_path = sejong_home / "state" / "active-context.json"
            legacy_path.parent.mkdir(parents=True)
            legacy = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            legacy["repo_id"] = "legacy-invalid-shape"
            legacy["run_id"] = "legacy-invalid-shape"
            legacy.pop("last_user_intent")
            legacy_bytes = (json.dumps(legacy, sort_keys=True) + "\n").encode()
            legacy_path.write_bytes(legacy_bytes)
            candidate = (
                sejong_home
                / "runs"
                / "legacy-invalid-shape"
                / "legacy-invalid-shape"
                / "king-sejong-context.json"
            )

            # When: migration evaluates the otherwise usable legacy record.
            migrated = run_context(["migrate-legacy"], sejong_home)
            receipt = json.loads(
                (sejong_home / "state" / "legacy-active-context-migration.json").read_text(encoding="utf-8")
            )
            preserved_bytes = legacy_path.read_bytes()

        # Then: the record and receipt survive but invalid durable state is not derived.
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertEqual(preserved_bytes, legacy_bytes)
        self.assertFalse(candidate.exists())
        self.assertIsNone(receipt["context_ref"])
        self.assertFalse(receipt["context_materialized"])
        self.assertFalse(receipt["repo_index_updated"])

    def test_unbind_tombstone_blocks_stale_resurrection(self) -> None:
        # Given: session A is bound and a stale writer remembers revision 1.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="unbind-run",
                session_id="session-a",
                intent="unbind intent",
            )

            # When: the session is explicitly unbound, then a stale resume races afterward.
            unbound = run_context(
                ["unbind", "--session-id", "session-a", "--turn-id", "turn-unbind", "--expect-revision", "1"],
                sejong_home,
            )
            stale_resume = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-stale-resume",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-after-unbind"), sejong_home)
            binding_paths = list((sejong_home / "state" / "session-bindings").glob("*.json"))
            binding = json.loads(binding_paths[0].read_text(encoding="utf-8"))

        # Then: the tombstone remains authoritative and the stale resume is rejected.
        self.assertEqual(unbound.returncode, 0, unbound.stderr)
        self.assertNotEqual(stale_resume.returncode, 0)
        self.assertIn("binding revision conflict", stale_resume.stdout + stale_resume.stderr)
        self.assertEqual(binding["state"], "unbound")
        self.assertEqual(binding["binding_epoch"], 2)
        self.assertEqual(output, {})

    def test_late_old_hook_observation_cannot_modify_replacement_binding(self) -> None:
        # Given: session A captured context A epoch 1 before switching to context B.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="late-a",
                session_id="session-a",
                intent="late A intent",
            )
            context_b = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="late-b",
                session_id="session-b",
                intent="late B intent",
            )
            switched = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-switch",
                    "--context",
                    str(context_b),
                    "--expect-revision",
                    "1",
                ],
                sejong_home,
            )

            # When: the earlier hook attempts to publish its now-stale observation token.
            late = run_context(
                [
                    "observe",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-old-late",
                    "--expect-context-id",
                    "ctx-late-a",
                    "--expect-binding-epoch",
                    "1",
                ],
                sejong_home,
            )
            output = run_hook("UserPromptSubmit", prompt_payload("session-a", "turn-current"), sejong_home)

        # Then: stale observation is rejected and context B remains foreground.
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertNotEqual(late.returncode, 0)
        self.assertIn("stale binding observation", late.stdout + late.stderr)
        self.assertIn("active_context_id=ctx-late-b", additional_context(output))
        self.assertNotIn("ctx-late-a", additional_context(output))

    def test_stale_binding_revision_is_rejected(self) -> None:
        # Given: session A already has binding revision 1.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            context_path = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="cas-run",
                session_id="session-a",
                intent="CAS intent",
            )

            # When: a stale writer attempts replacement with generation 0.
            result = run_context(
                [
                    "resume",
                    "--session-id",
                    "session-a",
                    "--turn-id",
                    "turn-stale",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "0",
                ],
                sejong_home,
            )

        # Then: the update fails with an explicit revision-conflict result.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("binding revision conflict", result.stdout + result.stderr)

    def test_concurrent_binding_replacements_detect_exactly_one_revision_conflict(self) -> None:
        # Given: two replacement writers hold the same observed binding revision.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="race-a",
                session_id="session-a",
                intent="race A intent",
            )
            context_b = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="race-b",
                session_id="session-b",
                intent="race B intent",
            )
            context_c = start_context(
                sejong_home,
                repo_root=REPO_ROOT,
                run_id="race-c",
                session_id="session-c",
                intent="race C intent",
            )
            environment = {
                **os.environ,
                "SEJONG_HOME": str(sejong_home),
                "SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS": "2.0",
            }
            commands = [
                [
                    sys.executable,
                    str(CONTEXT_SCRIPT),
                    "resume",
                    "--session-id",
                    "session-a",
                    "--context",
                    str(context_path),
                    "--expect-revision",
                    "1",
                ]
                for context_path in (context_b, context_c)
            ]

            # When: both writers race through the per-session lock and CAS boundary.
            processes = [
                subprocess.Popen(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(REPO_ROOT),
                    env=environment,
                )
                for command in commands
            ]
            results = []
            for process in processes:
                stdout, stderr = process.communicate()
                results.append((process.returncode, stdout, stderr))
            bindings = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (sejong_home / "state" / "session-bindings").glob("*.json")
            ]
            binding = next(item for item in bindings if item.get("session_id") == "session-a")

        # Then: one atomic replacement wins and the other observes a deterministic CAS conflict.
        self.assertEqual(sum(returncode == 0 for returncode, _, _ in results), 1)
        self.assertEqual(sum(returncode != 0 for returncode, _, _ in results), 1)
        self.assertTrue(
            any("binding revision conflict" in stdout + stderr for returncode, stdout, stderr in results if returncode)
        )
        self.assertIn(binding["active_context_id"], {"ctx-race-b", "ctx-race-c"})
        self.assertEqual(binding["revision"], 2)


if __name__ == "__main__":
    unittest.main()
