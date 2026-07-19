from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from codex_process_contract import CodexProcessRequest


class ProcessStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProcessResult:
    status: ProcessStatus
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool


class CodexProcess(Protocol):
    def run(self, request: CodexProcessRequest, cancellation_path: Path) -> ProcessResult: ...
