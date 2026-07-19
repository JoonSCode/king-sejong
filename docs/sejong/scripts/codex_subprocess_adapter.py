from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from codex_process_contract import CodexProcessRequest
from codex_process_runtime import ProcessResult, ProcessStatus


class RunningProcess(Protocol):
    returncode: int | None

    def communicate(self, input: str | None = None, timeout: float | None = None) -> tuple[str, str]: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...


class ProcessLauncher(Protocol):
    def start(self, request: CodexProcessRequest) -> RunningProcess: ...


@dataclass(frozen=True, slots=True)
class SubprocessLauncher:
    def start(self, request: CodexProcessRequest) -> RunningProcess:
        return subprocess.Popen(
            request.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=request.cwd,
            shell=False,
        )


def _stop(process: RunningProcess) -> tuple[str, str]:
    process.terminate()
    try:
        return process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.communicate()


@dataclass(frozen=True, slots=True)
class SubprocessCodexProcess:
    launcher: ProcessLauncher = field(default_factory=SubprocessLauncher)
    poll_interval_seconds: float = 0.25

    def run(self, request: CodexProcessRequest, cancellation_path: Path) -> ProcessResult:
        if cancellation_path.exists():
            return ProcessResult(ProcessStatus.CANCELLED, None, "", "", False)
        try:
            process = self.launcher.start(request)
        except OSError as exc:
            return ProcessResult(ProcessStatus.FAILED, None, "", str(exc), False)
        deadline = time.monotonic() + request.timeout_seconds
        stdin_text: str | None = request.stdin_text
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stdout, stderr = _stop(process)
                return ProcessResult(ProcessStatus.TIMED_OUT, None, stdout, stderr, False)
            try:
                stdout, stderr = process.communicate(
                    input=stdin_text,
                    timeout=min(self.poll_interval_seconds, remaining),
                )
            except subprocess.TimeoutExpired:
                stdin_text = None
                if cancellation_path.exists():
                    stdout, stderr = _stop(process)
                    return ProcessResult(ProcessStatus.CANCELLED, None, stdout, stderr, False)
                continue
            status = ProcessStatus.COMPLETED if process.returncode == 0 else ProcessStatus.FAILED
            return ProcessResult(status, process.returncode, stdout, stderr, False)
