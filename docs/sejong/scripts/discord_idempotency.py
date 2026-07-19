from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Iterator, assert_never

from discord_control_contract import (
    ApproveTicketCommand,
    CancelTicketCommand,
    ControlContractError,
    CreateTicketCommand,
    InboundEvent,
    JsonObject,
    JsonValue,
    StatusTicketCommand,
)


FORMAT: Final[str] = "sejong.discord-idempotency/v0.1-draft"


class IdempotencyStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class IdempotencyDecision:
    status: IdempotencyStatus
    event_id: str
    idempotency_key: str
    ticket_id: str


def _ticket_id(event: InboundEvent) -> str:
    match event.command:
        case CreateTicketCommand(ticket=ticket):
            return ticket.ticket_id
        case ApproveTicketCommand(ticket_id=ticket_id):
            return ticket_id
        case CancelTicketCommand(ticket_id=ticket_id):
            return ticket_id
        case StatusTicketCommand(ticket_id=ticket_id):
            return ticket_id
        case unreachable:
            assert_never(unreachable)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(frozen=True, slots=True)
class IdempotencyStore:
    path: Path

    @classmethod
    def from_environment(cls) -> IdempotencyStore:
        explicit = os.environ.get("SEJONG_HOME")
        if explicit:
            root = Path(explicit)
        else:
            codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
            root = codex_home / "sejong"
        return cls(root / "state" / "discord" / "idempotency.json")

    def accept(self, event: InboundEvent) -> IdempotencyDecision:
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with _locked(lock_path):
            payload = self._load()
            records = payload["records"]
            if not isinstance(records, list):
                raise ControlContractError("corrupt_state", "idempotency records must be an array")
            ticket_id = _ticket_id(event)
            for item in records:
                if not isinstance(item, dict):
                    raise ControlContractError("corrupt_state", "idempotency record must be an object")
                same_key = item.get("idempotency_key") == event.idempotency_key
                same_event = item.get("event_id") == event.event_id
                if same_key or same_event:
                    expected = (event.event_id, event.idempotency_key, ticket_id)
                    actual = (item.get("event_id"), item.get("idempotency_key"), item.get("ticket_id"))
                    if actual != expected:
                        raise ControlContractError("idempotency_conflict", "event or key was already bound differently")
                    return IdempotencyDecision(IdempotencyStatus.DUPLICATE, *expected)
            record: JsonObject = {
                "event_id": event.event_id,
                "idempotency_key": event.idempotency_key,
                "ticket_id": ticket_id,
            }
            records.append(record)
            self._save(payload)
            return IdempotencyDecision(
                IdempotencyStatus.ACCEPTED,
                event.event_id,
                event.idempotency_key,
                ticket_id,
            )

    def _load(self) -> JsonObject:
        if not self.path.exists():
            return {"format": FORMAT, "records": []}
        try:
            loaded: JsonValue = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlContractError("corrupt_state", f"cannot read idempotency state: {exc}") from exc
        if not isinstance(loaded, dict) or loaded.get("format") != FORMAT:
            raise ControlContractError("corrupt_state", "idempotency state has unexpected format")
        return loaded

    def _save(self, payload: JsonObject) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)
