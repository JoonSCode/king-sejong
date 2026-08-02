#!/usr/bin/env python3
# noqa: SIZE_OK -- runtime lock primitive is intentionally reviewed as one atomic helper
from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Final, TypeAlias


LOCK_FORMAT: Final = "sejong.runtime-lock/v0.1-draft"
LOCK_NAME_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DEFAULT_TIMEOUT_SECONDS: Final = 5.0
DEFAULT_STALE_AFTER_SECONDS: Final = 30.0 * 60.0
DEFAULT_RETRY_INTERVAL_SECONDS: Final = 0.05

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class RuntimeLockClass(StrEnum):
    ACTIVE_POINTER = "active-pointer"
    SESSION_BINDING = "session-binding"
    REPO_INDEX = "repo-index"
    RUN_CONTEXT = "run-context"
    ARTIFACT_REF = "artifact-ref"
    TEAM_MAILBOX = "team-mailbox"
    TEAM_LEASE = "team-lease"
    CLEANUP = "cleanup"
    INSTALL_MAINTENANCE = "install-maintenance"


@dataclass(frozen=True, slots=True)
class RuntimeLockRequest:
    sejong_home: Path | None
    lock_name: str
    lock_class: RuntimeLockClass
    owner_session_id: str
    owner_device_id: str
    operation: str
    owner_run_id: str | None = None
    repo_id: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS
    retry_interval_seconds: float = DEFAULT_RETRY_INTERVAL_SECONDS


@dataclass(frozen=True, slots=True)
class InvalidRuntimeLockName(Exception):
    lock_name: str

    def __str__(self) -> str:
        return f"invalid runtime lock name: {self.lock_name!r}"


@dataclass(frozen=True, slots=True)
class InvalidRuntimeLockTimeout(Exception):
    timeout_seconds: float

    def __str__(self) -> str:
        return f"invalid runtime lock timeout: {self.timeout_seconds!r}; expected a finite value greater than 0"


@dataclass(frozen=True, slots=True)
class InvalidRuntimeLockStaleAfterSeconds(Exception):
    stale_after_seconds: float

    def __str__(self) -> str:
        return (
            f"invalid runtime lock stale threshold: {self.stale_after_seconds!r}; "
            "expected a finite value greater than 0"
        )


@dataclass(frozen=True, slots=True)
class InvalidRuntimeLockRetryIntervalSeconds(Exception):
    retry_interval_seconds: float

    def __str__(self) -> str:
        return (
            f"invalid runtime lock retry interval: {self.retry_interval_seconds!r}; "
            "expected a finite value greater than 0"
        )


@dataclass(frozen=True, slots=True)
class RuntimeLockTimeout(Exception):
    lock_name: str
    lock_class: RuntimeLockClass
    waited_seconds: float
    owner_session_id: str
    owner_run_id: str | None
    owner_device_id: str
    operation: str | None

    def __str__(self) -> str:
        return (
            f"timed out acquiring {self.lock_class.value} lock {self.lock_name!r} "
            f"after {self.waited_seconds:.3f}s; owner_session_id={self.owner_session_id}; "
            f"owner_run_id={self.owner_run_id or '<none>'}; "
            f"owner_device_id={self.owner_device_id}; operation={self.operation or '<unknown>'}"
        )


@dataclass(frozen=True, slots=True)
class RuntimeLockReleaseError(Exception):
    lock_name: str
    owner_session_id: str
    current_owner_session_id: str

    def __str__(self) -> str:
        return (
            f"refusing to release runtime lock {self.lock_name!r}; "
            f"held token owner={self.owner_session_id}, current owner={self.current_owner_session_id}"
        )


@dataclass(frozen=True, slots=True)
class RuntimeLock:
    path: Path
    token: str
    lock_name: str
    owner_session_id: str

    def release(self) -> None:
        record = read_lock_record(self.path)
        if record is None:
            return
        current_token = record.get("token")
        current_owner = value_as_str(record.get("owner_session_id"), "<unknown>")
        if current_token != self.token:
            raise RuntimeLockReleaseError(self.lock_name, self.owner_session_id, current_owner)
        remove_owned_lock_file(self)


def remove_owned_lock_file(lock: RuntimeLock) -> None:
    guard_path = lock.path.with_name(f"{lock.path.name}.stale-break")
    try:
        descriptor = os.open(guard_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    os.close(descriptor)
    temp_path = lock.path.with_name(f".{lock.path.name}.{uuid.uuid4().hex}.release")
    try:
        try:
            lock.path.rename(temp_path)
        except FileNotFoundError:
            return
        record = read_lock_record(temp_path)
        current_token = record.get("token") if record is not None else None
        current_owner = value_as_str(record.get("owner_session_id") if record is not None else None, "<unknown>")
        if current_token != lock.token:
            temp_path.replace(lock.path)
            raise RuntimeLockReleaseError(lock.lock_name, lock.owner_session_id, current_owner)
        remove_stale_break_guard(temp_path)
    finally:
        remove_stale_break_guard(guard_path)

def acquire_runtime_lock(request: RuntimeLockRequest) -> RuntimeLock:
    validate_lock_name(request.lock_name)
    validate_timeout_seconds(request.timeout_seconds)
    validate_stale_after_seconds(request.stale_after_seconds)
    validate_retry_interval_seconds(request.retry_interval_seconds)
    lock_path = lock_file_path(request.sejong_home, request.lock_name)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    guard_path = lock_path.with_name(f"{lock_path.name}.stale-break")
    started = time.monotonic()

    while True:
        if guard_path.exists():
            wait_for_retry(request, started, read_lock_record(lock_path))
            continue
        token = uuid.uuid4().hex
        record = build_lock_record(request, token, None)
        try:
            write_new_lock_file(lock_path, record)
            return RuntimeLock(lock_path, token, request.lock_name, request.owner_session_id)
        except FileExistsError:
            current = read_lock_record(lock_path)
            stale_reason = stale_lock_reason(current, lock_path, request.stale_after_seconds)
            if stale_reason is not None:
                stale_record = dict(current or {"owner_session_id": "<unknown>"})
                stale_record["stale_break_reason"] = stale_reason
                replacement = build_lock_record(request, token, stale_record)
                if replace_stale_lock(lock_path, current, replacement):
                    return RuntimeLock(lock_path, token, request.lock_name, request.owner_session_id)
                continue
            wait_for_retry(request, started, current)


def validate_lock_name(lock_name: str) -> None:
    if LOCK_NAME_PATTERN.fullmatch(lock_name) is None:
        raise InvalidRuntimeLockName(lock_name)


def validate_timeout_seconds(timeout_seconds: float) -> None:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
        raise InvalidRuntimeLockTimeout(timeout_seconds)


def validate_stale_after_seconds(stale_after_seconds: float) -> None:
    if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0.0:
        raise InvalidRuntimeLockStaleAfterSeconds(stale_after_seconds)


def validate_retry_interval_seconds(retry_interval_seconds: float) -> None:
    if not math.isfinite(retry_interval_seconds) or retry_interval_seconds <= 0.0:
        raise InvalidRuntimeLockRetryIntervalSeconds(retry_interval_seconds)


def lock_file_path(sejong_home: Path | None, lock_name: str) -> Path:
    root = sejong_home if sejong_home is not None else default_sejong_home()
    return root.expanduser() / "state" / "locks" / f"{lock_name}.lock"


def default_sejong_home() -> Path:
    configured = os.environ.get("SEJONG_HOME")
    if configured:
        return Path(configured)
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def build_lock_record(request: RuntimeLockRequest, token: str, stale_record: JsonObject | None) -> JsonObject:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    record: JsonObject = {
        "format": LOCK_FORMAT,
        "lock_name": request.lock_name,
        "lock_class": request.lock_class.value,
        "owner_session_id": request.owner_session_id,
        "owner_run_id": request.owner_run_id,
        "repo_id": request.repo_id,
        "owner_device_id": request.owner_device_id,
        "owner_host": socket.gethostname(),
        "owner_process_id": os.getpid(),
        "operation": request.operation,
        "token": token,
        "created_at": timestamp,
        "heartbeat_at": timestamp,
        "stale_after_seconds": request.stale_after_seconds,
    }
    if stale_record is not None:
        previous_owner = value_as_str(stale_record.get("owner_session_id"), "<unknown>")
        record["stale_previous_owner_session_id"] = previous_owner
        record["stale_break_reason"] = value_as_str(stale_record.get("stale_break_reason"), "stale")
    return record


def write_new_lock_file(path: Path, record: JsonObject) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")


def read_lock_record(path: Path) -> JsonObject | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return {"format": "malformed", "stale_break_reason": "malformed lock metadata"}
    if not isinstance(loaded, dict):
        return {"format": "malformed", "stale_break_reason": "non-mapping lock metadata"}
    return {key: item if json_is_compatible(item) else str(item) for key, item in loaded.items() if isinstance(key, str)}


def json_is_compatible(value: JsonValue) -> bool:
    return isinstance(value, str | list | dict) or type(value) in {int, float, bool} or value is None


def stale_lock_reason(record: JsonObject | None, path: Path, stale_after_seconds: float) -> str | None:
    if record is None:
        return None
    process_id = record.get("owner_process_id")
    if type(process_id) is int and process_id > 0 and not process_is_running(process_id):
        return "owner process is gone"
    timestamp = record.get("heartbeat_at") or record.get("created_at")
    parsed = parse_utc(timestamp)
    if parsed is not None and (datetime.now(timezone.utc) - parsed).total_seconds() >= stale_after_seconds:
        return "lock age exceeds stale threshold"
    if parsed is None and file_age_seconds(path) >= stale_after_seconds:
        return value_as_str(record.get("stale_break_reason"), "lock metadata is stale or malformed")
    return None


def process_is_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_utc(value: JsonValue) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def file_age_seconds(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def replace_stale_lock(path: Path, observed: JsonObject | None, replacement: JsonObject) -> bool:
    guard_path = path.with_name(f"{path.name}.stale-break")
    try:
        descriptor = os.open(guard_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    os.close(descriptor)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        if read_lock_record(path) != observed:
            return False
        write_new_lock_file(temp_path, replacement)
        os.replace(temp_path, path)
    except (FileExistsError, FileNotFoundError):
        return False
    finally:
        remove_stale_break_guard(temp_path)
        remove_stale_break_guard(guard_path)
    return True


def remove_stale_break_guard(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def timeout_error(request: RuntimeLockRequest, waited: float, record: JsonObject | None) -> RuntimeLockTimeout:
    owner_session = value_as_str(record.get("owner_session_id") if record is not None else None, "<unknown>")
    owner_run = value_as_str(record.get("owner_run_id") if record is not None else None, "") or None
    owner_device = value_as_str(record.get("owner_device_id") if record is not None else None, "<unknown>")
    operation = value_as_str(record.get("operation") if record is not None else None, "") or None
    return RuntimeLockTimeout(
        request.lock_name,
        request.lock_class,
        waited,
        owner_session,
        owner_run,
        owner_device,
        operation,
    )


def value_as_str(value: JsonValue, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def wait_for_retry(request: RuntimeLockRequest, started: float, record: JsonObject | None) -> None:
    waited = time.monotonic() - started
    if waited >= request.timeout_seconds:
        raise timeout_error(request, waited, record) from None
    time.sleep(min(request.retry_interval_seconds, max(0.0, request.timeout_seconds - waited)))
