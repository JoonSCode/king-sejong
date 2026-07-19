from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias


JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class RiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SandboxMode(StrEnum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"


@dataclass(frozen=True, slots=True)
class TicketIntent:
    ticket_id: str
    objective: str
    host_id: str
    repo_id: str
    task_class: str
    risk_class: RiskClass
    model: str
    sandbox: SandboxMode
    timeout_seconds: int
    read_paths: tuple[str, ...]
    write_paths: tuple[str, ...]
    verification_requirements: tuple[str, ...]
    dry_run: bool


@dataclass(frozen=True, slots=True)
class CreateTicketCommand:
    ticket: TicketIntent


@dataclass(frozen=True, slots=True)
class ApproveTicketCommand:
    ticket_id: str
    approval_ref: str


@dataclass(frozen=True, slots=True)
class CancelTicketCommand:
    ticket_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class StatusTicketCommand:
    ticket_id: str


ControlCommand: TypeAlias = (
    CreateTicketCommand | ApproveTicketCommand | CancelTicketCommand | StatusTicketCommand
)


@dataclass(frozen=True, slots=True)
class InboundEvent:
    event_id: str
    idempotency_key: str
    received_at: str
    guild_id: str
    channel_id: str
    actor_user_id: str
    command: ControlCommand


@dataclass(slots=True)
class ControlContractError(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"
