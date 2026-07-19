from __future__ import annotations

import re
from typing import Final

from discord_contract_parsing import (
    boolean_value,
    exact_fields,
    object_value,
    positive_integer,
    text_tuple,
    text_value,
)
from discord_contract_types import (
    ControlContractError,
    JsonValue,
    RiskClass,
    SandboxMode,
    TicketIntent,
)


TICKET_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "ticket_id",
        "objective",
        "target",
        "task_class",
        "risk_class",
        "model",
        "sandbox",
        "timeout_seconds",
        "scope",
        "verification_requirements",
        "dry_run",
    }
)
SAFE_MODEL_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def parse_ticket(value: JsonValue) -> TicketIntent:
    ticket = object_value(value, "command.ticket")
    exact_fields(ticket, TICKET_FIELDS, "command.ticket")
    target = object_value(ticket.get("target"), "command.ticket.target")
    exact_fields(target, frozenset({"host_id", "repo_id"}), "command.ticket.target")
    scope = object_value(ticket.get("scope"), "command.ticket.scope")
    exact_fields(scope, frozenset({"read_paths", "write_paths"}), "command.ticket.scope")
    model = text_value(ticket.get("model"), "command.ticket.model")
    if SAFE_MODEL_PATTERN.fullmatch(model) is None:
        raise ControlContractError("unsafe_command", "model must be one opaque argv-safe token")
    try:
        risk_class = RiskClass(text_value(ticket.get("risk_class"), "command.ticket.risk_class"))
        sandbox = SandboxMode(text_value(ticket.get("sandbox"), "command.ticket.sandbox"))
    except ValueError as exc:
        raise ControlContractError("malformed_input", f"unsupported ticket enum: {exc}") from exc
    return TicketIntent(
        ticket_id=text_value(ticket.get("ticket_id"), "command.ticket.ticket_id"),
        objective=text_value(ticket.get("objective"), "command.ticket.objective"),
        host_id=text_value(target.get("host_id"), "command.ticket.target.host_id"),
        repo_id=text_value(target.get("repo_id"), "command.ticket.target.repo_id"),
        task_class=text_value(ticket.get("task_class"), "command.ticket.task_class"),
        risk_class=risk_class,
        model=model,
        sandbox=sandbox,
        timeout_seconds=positive_integer(ticket.get("timeout_seconds"), "command.ticket.timeout_seconds"),
        read_paths=text_tuple(scope.get("read_paths"), "command.ticket.scope.read_paths"),
        write_paths=text_tuple(scope.get("write_paths"), "command.ticket.scope.write_paths"),
        verification_requirements=text_tuple(
            ticket.get("verification_requirements"),
            "command.ticket.verification_requirements",
        ),
        dry_run=boolean_value(ticket.get("dry_run"), "command.ticket.dry_run"),
    )
