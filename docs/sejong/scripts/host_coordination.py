from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator

from discord_contract_types import ControlContractError, JsonObject, JsonValue


class HostStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class CodexAuthState(StrEnum):
    OBSERVED_READY = "observed_ready"
    OBSERVED_MISSING = "observed_missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HostObservation:
    host_id: str
    observed_at: str
    status: HostStatus
    codex_auth: CodexAuthState
    capabilities: tuple[str, ...]
    repo_paths: tuple[tuple[str, str], ...]


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
class HostStateStore:
    sejong_home: Path

    @property
    def path(self) -> Path:
        return self.sejong_home / "state" / "discord" / "hosts.json"

    def record_heartbeat(self, observation: HostObservation) -> Path:
        if not observation.host_id or not observation.observed_at:
            raise ControlContractError("invalid_heartbeat", "host and observation time are required")
        if len(set(observation.capabilities)) != len(observation.capabilities):
            raise ControlContractError("invalid_heartbeat", "host capabilities must be unique")
        repo_paths = dict(observation.repo_paths)
        if len(repo_paths) != len(observation.repo_paths):
            raise ControlContractError("invalid_heartbeat", "repository mappings must be unique")
        if any(not Path(value).is_absolute() for value in repo_paths.values()):
            raise ControlContractError("invalid_heartbeat", "repository mappings must be absolute")
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with _locked(lock_path):
            payload = self._load()
            hosts = payload["hosts"]
            if not isinstance(hosts, list):
                raise ControlContractError("corrupt_state", "host records must be an array")
            record: JsonObject = {
                "host_id": observation.host_id,
                "observed_at": observation.observed_at,
                "status": observation.status.value,
                "codex_auth": observation.codex_auth.value,
                "capabilities": list(observation.capabilities),
                "repo_paths": repo_paths,
            }
            remaining = [item for item in hosts if isinstance(item, dict) and item.get("host_id") != observation.host_id]
            payload["hosts"] = [*remaining, record]
            self._save(payload)
        return self.path

    def _load(self) -> JsonObject:
        if not self.path.exists():
            return {"format": "sejong.discord-host-state/v0.1-draft", "hosts": []}
        try:
            loaded: JsonValue = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlContractError("corrupt_state", f"cannot read host state: {exc}") from exc
        if not isinstance(loaded, dict) or loaded.get("format") != "sejong.discord-host-state/v0.1-draft":
            raise ControlContractError("corrupt_state", "host state has unexpected format")
        return loaded

    def _save(self, payload: JsonObject) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)


@dataclass(frozen=True, slots=True)
class WriteLeaseRequest:
    lease_id: str
    ticket_id: str
    host_id: str
    repo_id: str
    workspace: Path
    acquired_at: str
    expires_at: str
    host_status: HostStatus


@dataclass(frozen=True, slots=True)
class WriteLeaseStore:
    sejong_home: Path

    @property
    def path(self) -> Path:
        return self.sejong_home / "state" / "discord" / "write-leases.json"

    def acquire(self, request: WriteLeaseRequest, *, observed_at: str | None = None) -> JsonObject:
        if request.host_status is HostStatus.DISCONNECTED:
            raise ControlContractError("host_disconnected", "write lease host is disconnected")
        if request.host_status is HostStatus.UNKNOWN:
            raise ControlContractError("host_state_unknown", "write lease host state is unknown")
        if not request.workspace.is_absolute():
            raise ControlContractError("invalid_lease", "lease workspace must be absolute")
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with _locked(lock_path):
            payload = self._load()
            leases = payload["leases"]
            if not isinstance(leases, list):
                raise ControlContractError("corrupt_state", "write leases must be an array")
            if any(isinstance(item, dict) and item.get("lease_id") == request.lease_id for item in leases):
                raise ControlContractError("duplicate_lease", "write lease id is already bound")
            active = next((
                item for item in leases
                if isinstance(item, dict)
                and item.get("status") == "active"
                and item.get("repo_id") == request.repo_id
            ), None)
            if active is not None:
                expired = observed_at is not None and str(active.get("expires_at", "")) <= observed_at
                code = "lease_recovery_required" if expired else "write_collision"
                raise ControlContractError(code, "repository already has an unresolved active write lease")
            record: JsonObject = {
                "lease_id": request.lease_id,
                "ticket_id": request.ticket_id,
                "host_id": request.host_id,
                "repo_id": request.repo_id,
                "workspace": str(request.workspace),
                "acquired_at": request.acquired_at,
                "heartbeat_at": request.acquired_at,
                "expires_at": request.expires_at,
                "status": "active",
                "isolation_claim": "edit_isolation_only",
            }
            leases.append(record)
            self._save(payload)
            return record

    def recover_release(
        self,
        lease_id: str,
        ticket_id: str,
        *,
        released_at: str,
        evidence_ref: str,
    ) -> None:
        if not evidence_ref:
            raise ControlContractError("recovery_evidence_required", "lease recovery requires evidence")
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with _locked(lock_path):
            payload = self._load()
            leases = payload["leases"]
            if not isinstance(leases, list):
                raise ControlContractError("corrupt_state", "write leases must be an array")
            active = next((
                item for item in leases
                if isinstance(item, dict)
                and item.get("lease_id") == lease_id
                and item.get("status") == "active"
            ), None)
            if active is None or active.get("ticket_id") != ticket_id:
                raise ControlContractError("invalid_recovery", "active lease and ticket do not match")
            active["status"] = "released"
            active["released_at"] = released_at
            active["recovery_evidence_ref"] = evidence_ref
            self._save(payload)

    def _load(self) -> JsonObject:
        if not self.path.exists():
            return {"format": "sejong.discord-write-leases/v0.1-draft", "leases": []}
        try:
            loaded: JsonValue = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlContractError("corrupt_state", f"cannot read write leases: {exc}") from exc
        if not isinstance(loaded, dict) or loaded.get("format") != "sejong.discord-write-leases/v0.1-draft":
            raise ControlContractError("corrupt_state", "write leases have unexpected format")
        return loaded

    def _save(self, payload: JsonObject) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)
