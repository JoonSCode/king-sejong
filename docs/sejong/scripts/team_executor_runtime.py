from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Final


FORMAT: Final = "sejong.team-executor-preflight/v0.1-draft"
BACKEND: Final = "team_executor"
HEALTHY: Final = "healthy"
UNDETECTED: Final = "undetected"
UNHEALTHY: Final = "unhealthy"
TEAM_EXECUTOR_HEALTH_STATES: Final = {
    "unknown",
    HEALTHY,
    UNDETECTED,
    UNHEALTHY,
}


@dataclass(frozen=True, slots=True)
class TeamExecutorPreflight:
    format: str
    backend: str
    health: str
    executable: str | None
    version: str | None
    reason: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "format": self.format,
            "backend": self.backend,
            "health": self.health,
            "executable": self.executable,
            "version": self.version,
            "reason": self.reason,
        }


def _result(
    health: str,
    *,
    executable: str | None,
    version: str | None,
    reason: str,
) -> TeamExecutorPreflight:
    return TeamExecutorPreflight(
        format=FORMAT,
        backend=BACKEND,
        health=health,
        executable=executable,
        version=version,
        reason=reason,
    )


def fingerprint_team_executor(
    *,
    executable_name: str = "tmux",
    timeout_seconds: float = 5.0,
) -> TeamExecutorPreflight:
    executable = shutil.which(executable_name)
    if executable is None:
        return _result(
            UNDETECTED,
            executable=None,
            version=None,
            reason="tmux_executable_not_found",
        )

    try:
        probe = subprocess.run(
            [executable, "-V"],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _result(
            UNHEALTHY,
            executable=executable,
            version=None,
            reason="tmux_version_probe_timed_out",
        )
    except OSError:
        return _result(
            UNHEALTHY,
            executable=executable,
            version=None,
            reason="tmux_version_probe_os_error",
        )

    version = (probe.stdout.strip() or probe.stderr.strip()) or None
    if probe.returncode != 0:
        return _result(
            UNHEALTHY,
            executable=executable,
            version=version,
            reason="tmux_version_probe_failed",
        )
    if version is None:
        return _result(
            UNHEALTHY,
            executable=executable,
            version=None,
            reason="tmux_version_missing",
        )
    return _result(
        HEALTHY,
        executable=executable,
        version=version,
        reason="tmux_version_probe_succeeded",
    )
