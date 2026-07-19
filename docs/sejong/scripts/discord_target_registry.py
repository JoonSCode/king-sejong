from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, assert_never

from discord_control_contract import ControlContractError, JsonValue


JsonObject: TypeAlias = dict[str, JsonValue]


def _object(value: JsonValue, field: str) -> JsonObject:
    match value:
        case dict():
            return value
        case str() | int() | float() | bool() | None | list():
            raise ControlContractError("malformed_registry", f"{field} must be an object")
        case unreachable:
            assert_never(unreachable)


def _array(value: JsonValue, field: str) -> list[JsonValue]:
    match value:
        case list():
            return value
        case str() | int() | float() | bool() | None | dict():
            raise ControlContractError("malformed_registry", f"{field} must be an array")
        case unreachable:
            assert_never(unreachable)


def _text(value: JsonValue, field: str) -> str:
    match value:
        case str() if value:
            return value
        case str() | int() | float() | bool() | None | list() | dict():
            raise ControlContractError("malformed_registry", f"{field} must be non-empty text")
        case unreachable:
            assert_never(unreachable)


def _absolute_path(value: JsonValue, field: str) -> Path:
    path = Path(_text(value, field))
    if not path.is_absolute():
        raise ControlContractError("malformed_registry", f"{field} must be absolute")
    return path


@dataclass(frozen=True, slots=True)
class RepositoryMapping:
    repo_id: str
    repo_root: Path


@dataclass(frozen=True, slots=True)
class HostMapping:
    host_id: str
    enabled: bool
    codex_binary: Path
    repositories: tuple[RepositoryMapping, ...]


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    host_id: str
    repo_id: str
    repo_root: Path
    codex_binary: Path


@dataclass(frozen=True, slots=True)
class TargetRegistry:
    hosts: tuple[HostMapping, ...]

    @classmethod
    def load(cls, path: Path) -> TargetRegistry:
        try:
            raw: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlContractError("malformed_registry", f"cannot read target registry: {exc}") from exc
        payload = _object(raw, "registry")
        if set(payload) != {"format", "hosts"} or payload.get("format") != "sejong.discord-target-registry/v0.1-draft":
            raise ControlContractError("malformed_registry", "registry identity or fields are invalid")
        hosts = tuple(_parse_host(item) for item in _array(payload.get("hosts"), "hosts"))
        host_ids = tuple(host.host_id for host in hosts)
        if len(set(host_ids)) != len(host_ids):
            raise ControlContractError("malformed_registry", "host ids must be unique")
        return cls(hosts)

    def resolve(self, host_id: str, repo_id: str) -> ResolvedTarget:
        host = next((item for item in self.hosts if item.host_id == host_id), None)
        if host is None:
            raise ControlContractError("unknown_target", f"unknown host: {host_id}")
        if not host.enabled:
            raise ControlContractError("target_unavailable", f"host is disabled: {host_id}")
        repository = next((item for item in host.repositories if item.repo_id == repo_id), None)
        if repository is None:
            raise ControlContractError("unknown_target", f"unknown repository on {host_id}: {repo_id}")
        return ResolvedTarget(host.host_id, repository.repo_id, repository.repo_root, host.codex_binary)


def _parse_host(value: JsonValue) -> HostMapping:
    host = _object(value, "host")
    if set(host) != {"host_id", "enabled", "codex_binary", "repositories"}:
        raise ControlContractError("malformed_registry", "host fields are invalid")
    enabled = host.get("enabled")
    if not isinstance(enabled, bool):
        raise ControlContractError("malformed_registry", "host.enabled must be a boolean")
    repositories = tuple(
        _parse_repository(item) for item in _array(host.get("repositories"), "host.repositories")
    )
    repo_ids = tuple(repository.repo_id for repository in repositories)
    if len(set(repo_ids)) != len(repo_ids):
        raise ControlContractError("malformed_registry", "repository ids must be unique per host")
    return HostMapping(
        host_id=_text(host.get("host_id"), "host.host_id"),
        enabled=enabled,
        codex_binary=_absolute_path(host.get("codex_binary"), "host.codex_binary"),
        repositories=repositories,
    )


def _parse_repository(value: JsonValue) -> RepositoryMapping:
    repository = _object(value, "repository")
    if set(repository) != {"repo_id", "repo_root"}:
        raise ControlContractError("malformed_registry", "repository fields are invalid")
    return RepositoryMapping(
        repo_id=_text(repository.get("repo_id"), "repository.repo_id"),
        repo_root=_absolute_path(repository.get("repo_root"), "repository.repo_root"),
    )
