from __future__ import annotations

from typing import Final, assert_never

from discord_contract_parsing import exact_fields, object_value, text_set, text_value
from discord_contract_types import (
    ApproveTicketCommand,
    CancelTicketCommand,
    ControlContractError,
    CreateTicketCommand,
    InboundEvent,
    JsonObject,
    JsonValue,
    StatusTicketCommand,
)
from discord_ticket_contract import parse_ticket


FORBIDDEN_COMMAND_FIELDS: Final[frozenset[str]] = frozenset(
    {"argv", "command_text", "raw_command", "shell", "shell_command"}
)
EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {"format", "event_id", "idempotency_key", "received_at", "guild_id", "channel_id", "actor", "command"}
)
POLICY_FIELDS: Final[frozenset[str]] = frozenset(
    {"format", "allowed_guild_ids", "allowed_channel_ids", "allowed_user_ids", "required_role_ids"}
)


def _authorize(event: JsonObject, policy: JsonObject) -> None:
    exact_fields(policy, POLICY_FIELDS, "policy")
    if policy.get("format") != "sejong.discord-control-policy/v0.1-draft":
        raise ControlContractError("malformed_input", "unsupported control policy format")
    actor = object_value(event.get("actor"), "actor")
    allowed = (
        text_value(event.get("guild_id"), "guild_id")
        in text_set(policy.get("allowed_guild_ids"), "allowed_guild_ids")
        and text_value(event.get("channel_id"), "channel_id")
        in text_set(policy.get("allowed_channel_ids"), "allowed_channel_ids")
        and text_value(actor.get("user_id"), "actor.user_id")
        in text_set(policy.get("allowed_user_ids"), "allowed_user_ids")
        and text_set(policy.get("required_role_ids"), "required_role_ids").issubset(
            text_set(actor.get("role_ids"), "actor.role_ids")
        )
    )
    if not allowed:
        raise ControlContractError("unauthorized", "actor is outside the host-owned allowlist")


def parse_inbound_event(payload: JsonValue, policy: JsonValue) -> InboundEvent:
    match payload:
        case dict():
            command = payload.get("command")
        case str() | int() | float() | bool() | None | list():
            raise ControlContractError("malformed_input", "event must be an object")
        case unreachable:
            assert_never(unreachable)
    if not isinstance(command, dict):
        raise ControlContractError("malformed_input", "command must be an object")
    unsafe_fields = sorted(FORBIDDEN_COMMAND_FIELDS.intersection(command))
    if unsafe_fields:
        raise ControlContractError(
            "unsafe_command",
            f"raw process or shell fields are forbidden: {unsafe_fields}",
        )
    exact_fields(payload, EVENT_FIELDS, "event")
    if payload.get("format") != "sejong.discord-control-event/v0.1-draft":
        raise ControlContractError("malformed_input", "unsupported event format")
    actor = object_value(payload.get("actor"), "actor")
    exact_fields(actor, frozenset({"user_id", "role_ids"}), "actor")
    _authorize(payload, object_value(policy, "policy"))
    match text_value(command.get("kind"), "command.kind"):
        case "create_ticket":
            exact_fields(command, frozenset({"kind", "ticket"}), "command")
            parsed_command = CreateTicketCommand(parse_ticket(command.get("ticket")))
        case "approve":
            exact_fields(command, frozenset({"kind", "ticket_id", "approval_ref"}), "command")
            parsed_command = ApproveTicketCommand(
                ticket_id=text_value(command.get("ticket_id"), "command.ticket_id"),
                approval_ref=text_value(command.get("approval_ref"), "command.approval_ref"),
            )
        case "cancel":
            exact_fields(command, frozenset({"kind", "ticket_id", "reason"}), "command")
            parsed_command = CancelTicketCommand(
                ticket_id=text_value(command.get("ticket_id"), "command.ticket_id"),
                reason=text_value(command.get("reason"), "command.reason"),
            )
        case "status":
            exact_fields(command, frozenset({"kind", "ticket_id"}), "command")
            parsed_command = StatusTicketCommand(
                ticket_id=text_value(command.get("ticket_id"), "command.ticket_id")
            )
        case unsupported:
            raise ControlContractError("malformed_input", f"unsupported command kind: {unsupported}")
    return InboundEvent(
        event_id=text_value(payload.get("event_id"), "event_id"),
        idempotency_key=text_value(payload.get("idempotency_key"), "idempotency_key"),
        received_at=text_value(payload.get("received_at"), "received_at"),
        guild_id=text_value(payload.get("guild_id"), "guild_id"),
        channel_id=text_value(payload.get("channel_id"), "channel_id"),
        actor_user_id=text_value(actor.get("user_id"), "actor.user_id"),
        command=parsed_command,
    )
