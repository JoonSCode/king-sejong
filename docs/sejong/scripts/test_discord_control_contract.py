#!/usr/bin/env python3
from __future__ import annotations

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from typing import TypeAlias

import discord_control_contract as control
from discord_idempotency import IdempotencyStatus, IdempotencyStore
import discord_target_registry as targets


JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


def valid_policy() -> dict[str, JsonValue]:
    return {
        "format": "sejong.discord-control-policy/v0.1-draft",
        "allowed_guild_ids": ["guild-1"],
        "allowed_channel_ids": ["channel-1"],
        "allowed_user_ids": ["user-1"],
        "required_role_ids": ["operator"],
    }


def valid_event() -> dict[str, JsonValue]:
    return {
        "format": "sejong.discord-control-event/v0.1-draft",
        "event_id": "event-1",
        "idempotency_key": "discord:guild-1:event-1",
        "received_at": "2026-07-19T10:00:00Z",
        "guild_id": "guild-1",
        "channel_id": "channel-1",
        "actor": {"user_id": "user-1", "role_ids": ["operator"]},
        "command": {
            "kind": "create_ticket",
            "ticket": {
                "ticket_id": "ticket-1",
                "objective": "Update one bounded documentation file",
                "target": {"host_id": "mac-studio", "repo_id": "king-sejong"},
                "task_class": "implementation",
                "risk_class": "low",
                "model": "gpt-5.4",
                "sandbox": "workspace-write",
                "timeout_seconds": 900,
                "scope": {"read_paths": ["docs"], "write_paths": ["docs/example.md"]},
                "verification_requirements": ["git diff --check"],
                "dry_run": True,
            },
        },
    }


class DiscordControlContractTests(unittest.TestCase):
    def test_rejects_raw_shell_composition(self) -> None:
        # Given: an otherwise valid create-ticket event carries a raw shell escape hatch.
        event = valid_event()
        command = event["command"]
        assert isinstance(command, dict)
        command["raw_command"] = "codex exec ...; rm -rf target"

        # When: the untrusted Discord event crosses the Core adapter boundary.
        with self.assertRaises(control.ControlContractError) as raised:
            control.parse_inbound_event(event, valid_policy())

        # Then: raw command composition is rejected before a ticket exists.
        self.assertEqual(raised.exception.code, "unsafe_command")

    def test_rejects_actor_outside_host_owned_allowlist(self) -> None:
        # Given: a structurally valid Discord event comes from an unlisted actor.
        event = valid_event()
        actor = event["actor"]
        assert isinstance(actor, dict)
        actor["user_id"] = "unknown-user"

        # When: Core evaluates the actor against the separately supplied policy.
        with self.assertRaises(control.ControlContractError) as raised:
            control.parse_inbound_event(event, valid_policy())

        # Then: the adapter rejects the event without trusting inbound claims.
        self.assertEqual(raised.exception.code, "unauthorized")

    def test_parses_create_ticket_into_immutable_typed_command(self) -> None:
        # Given: a versioned and authorized create-ticket event.
        event = valid_event()

        # When: the adapter parses the trust boundary.
        parsed = control.parse_inbound_event(event, valid_policy())

        # Then: downstream code receives a fixed model and typed scope, not raw JSON.
        self.assertIsInstance(parsed.command, control.CreateTicketCommand)
        assert isinstance(parsed.command, control.CreateTicketCommand)
        self.assertEqual(parsed.command.ticket.model, "gpt-5.4")
        self.assertEqual(parsed.command.ticket.write_paths, ("docs/example.md",))
        self.assertTrue(parsed.command.ticket.dry_run)

    def test_parses_approval_cancel_and_status_commands(self) -> None:
        # Given: authorized lifecycle commands with their versioned payloads.
        cases: tuple[tuple[dict[str, JsonValue], type, str], ...] = (
            ({"kind": "approve", "ticket_id": "ticket-1", "approval_ref": "approval://ticket-1"}, control.ApproveTicketCommand, "approval://ticket-1"),
            ({"kind": "cancel", "ticket_id": "ticket-1", "reason": "superseded"}, control.CancelTicketCommand, "superseded"),
            ({"kind": "status", "ticket_id": "ticket-1"}, control.StatusTicketCommand, "ticket-1"),
        )

        for command, expected_type, expected_value in cases:
            with self.subTest(kind=command["kind"]):
                event = valid_event()
                event["command"] = command

                # When: the adapter parses the lifecycle command.
                parsed = control.parse_inbound_event(event, valid_policy())

                # Then: the command is a closed typed variant with no raw process field.
                self.assertIsInstance(parsed.command, expected_type)
                value = getattr(parsed.command, "approval_ref", None) or getattr(parsed.command, "reason", None) or parsed.command.ticket_id
                self.assertEqual(value, expected_value)

    def test_idempotency_store_deduplicates_under_sejong_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an isolated Sejong runtime root and one parsed Discord event.
            sejong_home = Path(tmp) / "sejong"
            home = Path(tmp) / "home"
            home.mkdir()
            parsed = control.parse_inbound_event(valid_event(), valid_policy())

            # When: the same event is accepted twice through the runtime store.
            with patch.dict(os.environ, {"HOME": str(home), "SEJONG_HOME": str(sejong_home)}, clear=True):
                store = IdempotencyStore.from_environment()
                first = store.accept(parsed)
                second = store.accept(parsed)

            # Then: only the first delivery is accepted and state stays outside the repo.
            self.assertEqual(first.status, IdempotencyStatus.ACCEPTED)
            self.assertEqual(second.status, IdempotencyStatus.DUPLICATE)
            self.assertEqual(store.path, sejong_home / "state" / "discord" / "idempotency.json")
            self.assertTrue(store.path.is_file())

    def test_target_registry_resolves_exact_host_repo_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a host-owned registry under an isolated Sejong runtime root.
            root = Path(tmp)
            sejong_home = root / "sejong"
            registry_path = sejong_home / "state" / "discord" / "targets.json"
            registry_path.parent.mkdir(parents=True)
            repo_root = root / "repo"
            repo_root.mkdir()
            registry_path.write_text(
                """{
  "format": "sejong.discord-target-registry/v0.1-draft",
  "hosts": [{
    "host_id": "mac-studio",
    "enabled": true,
    "codex_binary": "/opt/homebrew/bin/codex",
    "repositories": [{"repo_id": "king-sejong", "repo_root": "%s"}]
  }]
}\n""" % repo_root,
                encoding="utf-8",
            )

            # When: the ticket target is resolved by exact host and repository id.
            registry = targets.TargetRegistry.load(registry_path)
            target = registry.resolve("mac-studio", "king-sejong")

            # Then: Core returns only the sealed absolute mapping and executable.
            self.assertEqual(target.repo_root, repo_root)
            self.assertEqual(target.codex_binary, Path("/opt/homebrew/bin/codex"))

    def test_rejects_shell_metacharacters_in_model_token(self) -> None:
        # Given: a create-ticket event tries to smuggle shell syntax through model selection.
        event = valid_event()
        command = event["command"]
        assert isinstance(command, dict)
        ticket = command["ticket"]
        assert isinstance(ticket, dict)
        ticket["model"] = "gpt-5.4; touch /tmp/escaped"

        # When: the event crosses the typed control boundary.
        with self.assertRaises(control.ControlContractError) as raised:
            control.parse_inbound_event(event, valid_policy())

        # Then: only an opaque safe model token is accepted for argv construction.
        self.assertEqual(raised.exception.code, "unsafe_command")


if __name__ == "__main__":
    unittest.main()
