from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from discord_contract_types import ControlContractError, TicketIntent
from discord_target_registry import ResolvedTarget


DEFAULT_OUTPUT_LIMIT_BYTES: Final[int] = 1_048_576


@dataclass(frozen=True, slots=True)
class CodexProcessRequest:
    ticket_id: str
    model: str
    argv: tuple[str, ...]
    stdin_text: str
    cwd: Path
    timeout_seconds: int
    output_limit_bytes: int


def build_codex_process(
    ticket: TicketIntent,
    target: ResolvedTarget,
    workspace: Path,
) -> CodexProcessRequest:
    if (ticket.host_id, ticket.repo_id) != (target.host_id, target.repo_id):
        raise ControlContractError("target_mismatch", "ticket target does not match registry resolution")
    if not workspace.is_absolute():
        raise ControlContractError("unsafe_command", "workspace must be an absolute path")
    if not target.codex_binary.is_absolute():
        raise ControlContractError("unsafe_command", "Codex executable must be an absolute path")
    argv = (
        str(target.codex_binary),
        "exec",
        "--model",
        ticket.model,
        "--sandbox",
        ticket.sandbox.value,
        "--cd",
        str(workspace),
        "--ephemeral",
        "--json",
        "-",
    )
    return CodexProcessRequest(
        ticket_id=ticket.ticket_id,
        model=ticket.model,
        argv=argv,
        stdin_text=ticket.objective,
        cwd=workspace,
        timeout_seconds=ticket.timeout_seconds,
        output_limit_bytes=DEFAULT_OUTPUT_LIMIT_BYTES,
    )
