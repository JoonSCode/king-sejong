#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sejong_paths import path_contains_or_equals, repo_identity
from sejong_runtime_lock import (
    RuntimeLockClass,
    RuntimeLockReleaseError,
    RuntimeLockRequest,
    RuntimeLockTimeout,
    acquire_runtime_lock,
)


BINDING_FORMAT = "king-sejong.session-binding/v0.1"
REPO_INDEX_FORMAT = "king-sejong.repo-index/v0.1"
MIGRATION_FORMAT = "king-sejong.legacy-active-context-migration/v0.1"
ACTIVE_CONTEXT_STATES = {"active"}
DEFAULT_NAMESPACE = "codex"
DERIVED_STATE_WARNINGS_FIELD = "_king_sejong_derived_state_warnings"
REQUIRED_BINDING_FIELDS = (
    "format",
    "binding_id",
    "host_namespace",
    "session_id",
    "state",
    "context_ref",
    "active_context_id",
    "binding_epoch",
    "revision",
    "last_observation",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True, slots=True)
class BindingRevisionConflict(Exception):
    expected: int
    actual: int

    def __str__(self) -> str:
        return f"binding revision conflict: expected={self.expected}; actual={self.actual}"


@dataclass(frozen=True, slots=True)
class StaleBindingObservation(Exception):
    expected_context_id: str
    actual_context_id: str | None
    expected_epoch: int
    actual_epoch: int

    def __str__(self) -> str:
        return (
            "stale binding observation: "
            f"expected_context_id={self.expected_context_id}; actual_context_id={self.actual_context_id}; "
            f"expected_epoch={self.expected_epoch}; actual_epoch={self.actual_epoch}"
        )


class InvalidBinding(Exception):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_durable_context(context: dict[str, Any], context_ref: Path) -> None:
    # Imported lazily because sejong_context owns the durable Context contract
    # and imports this binding module for its CLI operations.
    from sejong_context import validate_context

    failures = validate_context(context)
    if failures:
        raise InvalidBinding(f"invalid durable context: {context_ref}: {', '.join(failures)}")


def session_key(session_id: str, namespace: str = DEFAULT_NAMESPACE) -> str:
    if not isinstance(session_id, str) or not session_id:
        raise InvalidBinding("session binding requires a non-empty session id")
    if not isinstance(namespace, str) or not namespace:
        raise InvalidBinding("session binding requires a non-empty host namespace")
    return hashlib.sha256(f"{namespace}\0{session_id}".encode("utf-8")).hexdigest()


def binding_path(sejong_home: Path, session_id: str, namespace: str = DEFAULT_NAMESPACE) -> Path:
    return sejong_home / "state" / "session-bindings" / f"{session_key(session_id, namespace)}.json"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _binding_lock(sejong_home: Path, session_id: str, namespace: str, operation: str):
    key = session_key(session_id, namespace)
    raw_timeout = os.environ.get("SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS", "2.0")
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as error:
        raise InvalidBinding(
            f"invalid SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS={raw_timeout!r}; expected a finite positive number"
        ) from error
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
        raise InvalidBinding(
            f"invalid SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS={raw_timeout!r}; expected a finite positive number"
        )
    return acquire_runtime_lock(
        RuntimeLockRequest(
            sejong_home=sejong_home,
            lock_name=f"session-binding-{key}",
            lock_class=RuntimeLockClass.SESSION_BINDING,
            owner_session_id=session_id,
            owner_device_id=socket.gethostname() or "local-device",
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
    )


def _load_binding_unlocked(sejong_home: Path, session_id: str, namespace: str) -> dict[str, Any] | None:
    path = binding_path(sejong_home, session_id, namespace)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, UnicodeError) as error:
        raise InvalidBinding(f"malformed session binding: {path}: {error}") from error
    if not isinstance(raw, dict):
        raise InvalidBinding(f"session binding must be an object: {path}")
    missing = [field for field in REQUIRED_BINDING_FIELDS if field not in raw]
    if missing:
        raise InvalidBinding(f"session binding is missing required fields {','.join(missing)}: {path}")
    if raw.get("format") != BINDING_FORMAT:
        raise InvalidBinding(f"unknown session binding format: {path}")
    if raw.get("host_namespace") != namespace or raw.get("session_id") != session_id:
        raise InvalidBinding(f"session binding identity mismatch: {path}")
    if raw.get("binding_id") != session_key(session_id, namespace):
        raise InvalidBinding(f"session binding filename identity mismatch: {path}")
    if raw.get("state") not in {"bound", "unbound"}:
        raise InvalidBinding(f"invalid session binding state: {path}")
    if raw["state"] == "bound" and (
        not isinstance(raw.get("context_ref"), str)
        or not raw["context_ref"]
        or not isinstance(raw.get("active_context_id"), str)
        or not raw["active_context_id"]
    ):
        raise InvalidBinding(f"bound session binding requires non-empty Context references: {path}")
    if raw["state"] == "unbound" and (
        raw.get("context_ref") is not None or raw.get("active_context_id") is not None
    ):
        raise InvalidBinding(f"unbound session binding must clear Context references: {path}")
    counters = (raw.get("binding_epoch"), raw.get("revision"))
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in counters):
        raise InvalidBinding(f"invalid session binding counters: {path}")
    if any(not isinstance(raw.get(field), str) or not raw[field] for field in ("created_at", "updated_at")):
        raise InvalidBinding(f"invalid session binding timestamps: {path}")
    observation = raw.get("last_observation")
    if observation is not None:
        if not isinstance(observation, dict) or "turn_id" not in observation or "observed_at" not in observation:
            raise InvalidBinding(f"invalid session binding observation: {path}")
        if observation.get("turn_id") is not None and not isinstance(observation.get("turn_id"), str):
            raise InvalidBinding(f"invalid session binding observation turn id: {path}")
        if observation.get("event_name") is not None and not isinstance(observation.get("event_name"), str):
            raise InvalidBinding(f"invalid session binding observation event name: {path}")
        if not isinstance(observation.get("observed_at"), str) or not observation["observed_at"]:
            raise InvalidBinding(f"invalid session binding observation timestamp: {path}")
    return raw


def load_binding(sejong_home: Path, session_id: str, namespace: str = DEFAULT_NAMESPACE) -> dict[str, Any] | None:
    return _load_binding_unlocked(sejong_home, session_id, namespace)


def _check_revision(current: dict[str, Any] | None, expected_revision: int | None) -> None:
    actual = int(current.get("revision", 0)) if current else 0
    if expected_revision is not None and expected_revision != actual:
        raise BindingRevisionConflict(expected_revision, actual)


def _history_record(sejong_home: Path, binding: dict[str, Any], status: str, turn_id: str | None) -> None:
    session_hash = str(binding["binding_id"])
    path = (
        sejong_home
        / "state"
        / "session-bindings"
        / "history"
        / session_hash
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}.json"
    )
    atomic_write_json(
        path,
        {
            "format": "king-sejong.session-binding-history/v0.1",
            "status": status,
            "host_namespace": binding["host_namespace"],
            "session_id": binding["session_id"],
            "context_ref": binding.get("context_ref"),
            "active_context_id": binding.get("active_context_id"),
            "binding_epoch": binding["binding_epoch"],
            "revision": binding["revision"],
            "turn_id": turn_id,
            "recorded_at": now_utc(),
        },
    )


def _derived_state_warning(label: str, error: Exception) -> str:
    return f"{label} failed after the authority commit: {type(error).__name__}: {error}"


def update_repo_index(sejong_home: Path, context: dict[str, Any], context_ref: Path) -> None:
    identities = context.get("repo_identities") or [repo_identity(context["repo_root"])]
    for identity in identities:
        digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()
        lock = acquire_runtime_lock(
            RuntimeLockRequest(
                sejong_home=sejong_home,
                lock_name=f"repo-index-{digest}",
                lock_class=RuntimeLockClass.REPO_INDEX,
                owner_session_id=str(context.get("session_id") or "indexer"),
                owner_device_id=socket.gethostname() or "local-device",
                operation="update repo index",
            )
        )
        try:
            path = sejong_home / "state" / "repo-index" / f"{digest}.json"
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError):
                existing = {"format": REPO_INDEX_FORMAT, "repo_identity": identity, "contexts": []}
            entries = [
                item
                for item in existing.get("contexts", [])
                if isinstance(item, dict) and item.get("active_context_id") != context.get("active_context_id")
            ]
            entries.append(
                {
                    "active_context_id": context.get("active_context_id"),
                    "context_ref": str(context_ref.resolve()),
                    "context_status": context.get("context_status", "active"),
                    "last_updated_at": context.get("last_updated_at"),
                }
            )
            atomic_write_json(
                path,
                {
                    "format": REPO_INDEX_FORMAT,
                    "repo_identity": identity,
                    "contexts": entries,
                    "rebuilt_at": now_utc(),
                },
            )
        finally:
            lock.release()


def bind_context(
    sejong_home: Path,
    session_id: str,
    context_ref: Path,
    *,
    turn_id: str | None = None,
    namespace: str = DEFAULT_NAMESPACE,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    context_ref = context_ref.expanduser().resolve()
    try:
        context = json.loads(context_ref.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError) as error:
        raise InvalidBinding(f"durable context is unavailable: {context_ref}: {error}") from error
    if not isinstance(context, dict) or not context.get("active_context_id"):
        raise InvalidBinding(f"invalid durable context: {context_ref}")
    _validate_durable_context(context, context_ref)
    if context.get("context_status", "active") not in ACTIVE_CONTEXT_STATES:
        raise InvalidBinding(f"context is not active: {context_ref}")
    lock = _binding_lock(sejong_home, session_id, namespace, "bind context")
    previous: dict[str, Any] | None = None
    try:
        current = _load_binding_unlocked(sejong_home, session_id, namespace)
        _check_revision(current, expected_revision)
        previous = dict(current) if current and current.get("state") == "bound" else None
        timestamp = now_utc()
        binding = {
            "format": BINDING_FORMAT,
            "binding_id": session_key(session_id, namespace),
            "host_namespace": namespace,
            "session_id": session_id,
            "state": "bound",
            "context_ref": str(context_ref),
            "active_context_id": context["active_context_id"],
            "binding_epoch": (
                int(current["binding_epoch"])
                if current
                and current.get("state") == "bound"
                and current.get("context_ref") == str(context_ref)
                and current.get("active_context_id") == context["active_context_id"]
                else int(current.get("binding_epoch", 0)) + 1 if current else 1
            ),
            "revision": int(current.get("revision", 0)) + 1 if current else 1,
            "last_observation": {"turn_id": turn_id, "observed_at": timestamp} if turn_id else None,
            "created_at": current.get("created_at", timestamp) if current else timestamp,
            "updated_at": timestamp,
        }
        atomic_write_json(binding_path(sejong_home, session_id, namespace), binding)
    finally:
        lock.release()
    warnings: list[str] = []
    if previous and previous.get("context_ref") != str(context_ref):
        try:
            _history_record(sejong_home, previous, "paused", turn_id)
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            warnings.append(_derived_state_warning("binding history update", error))
    try:
        update_repo_index(sejong_home, context, context_ref)
    except (
        InvalidBinding,
        RuntimeLockReleaseError,
        RuntimeLockTimeout,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        warnings.append(_derived_state_warning("repo index update", error))
    if warnings:
        binding[DERIVED_STATE_WARNINGS_FIELD] = warnings
    return binding


def unbind_session(
    sejong_home: Path,
    session_id: str,
    *,
    turn_id: str | None = None,
    namespace: str = DEFAULT_NAMESPACE,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    lock = _binding_lock(sejong_home, session_id, namespace, "unbind context")
    previous: dict[str, Any] | None = None
    try:
        current = _load_binding_unlocked(sejong_home, session_id, namespace)
        _check_revision(current, expected_revision)
        previous = dict(current) if current and current.get("state") == "bound" else None
        timestamp = now_utc()
        tombstone = {
            "format": BINDING_FORMAT,
            "binding_id": session_key(session_id, namespace),
            "host_namespace": namespace,
            "session_id": session_id,
            "state": "unbound",
            "context_ref": None,
            "active_context_id": None,
            "binding_epoch": (
                int(current["binding_epoch"])
                if current and current.get("state") == "unbound"
                else int(current.get("binding_epoch", 0)) + 1 if current else 1
            ),
            "revision": int(current.get("revision", 0)) + 1 if current else 1,
            "last_observation": {"turn_id": turn_id, "observed_at": timestamp} if turn_id else None,
            "created_at": current.get("created_at", timestamp) if current else timestamp,
            "updated_at": timestamp,
        }
        atomic_write_json(binding_path(sejong_home, session_id, namespace), tombstone)
    finally:
        lock.release()
    if previous:
        try:
            _history_record(sejong_home, previous, "paused", turn_id)
        except (OSError, TypeError, UnicodeError, ValueError) as error:
            tombstone[DERIVED_STATE_WARNINGS_FIELD] = [
                _derived_state_warning("binding history update", error)
            ]
    return tombstone


def observe_binding(
    sejong_home: Path,
    session_id: str,
    turn_id: str,
    expected_context_id: str,
    expected_epoch: int,
    *,
    event_name: str | None = None,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    lock = _binding_lock(sejong_home, session_id, namespace, "observe binding")
    try:
        current = _load_binding_unlocked(sejong_home, session_id, namespace)
        actual_context_id = current.get("active_context_id") if current else None
        actual_epoch = int(current.get("binding_epoch", 0)) if current else 0
        if (
            not current
            or current.get("state") != "bound"
            or actual_context_id != expected_context_id
            or actual_epoch != expected_epoch
        ):
            raise StaleBindingObservation(expected_context_id, actual_context_id, expected_epoch, actual_epoch)
        updated = dict(current)
        updated["revision"] = int(current["revision"]) + 1
        updated["last_observation"] = {
            "turn_id": turn_id,
            "event_name": event_name,
            "observed_at": now_utc(),
        }
        updated["updated_at"] = now_utc()
        atomic_write_json(binding_path(sejong_home, session_id, namespace), updated)
        return updated
    finally:
        lock.release()


def resolve_bound_context(
    sejong_home: Path,
    session_id: str,
    *,
    turn_id: str | None = None,
    event_name: str | None = None,
    namespace: str = DEFAULT_NAMESPACE,
    observe: bool = True,
) -> dict[str, Any]:
    lock = _binding_lock(sejong_home, session_id, namespace, "resolve binding")
    try:
        binding = _load_binding_unlocked(sejong_home, session_id, namespace)
        if not binding or binding.get("state") != "bound":
            return {}
        context_ref = binding.get("context_ref")
        if not isinstance(context_ref, str):
            raise InvalidBinding("bound session has no context_ref")
        try:
            context = json.loads(Path(context_ref).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError) as error:
            raise InvalidBinding(f"bound context is unavailable: {context_ref}: {error}") from error
        if not isinstance(context, dict) or context.get("active_context_id") != binding.get("active_context_id"):
            raise InvalidBinding(f"bound context identity mismatch: {context_ref}")
        if context.get("context_status", "active") not in ACTIVE_CONTEXT_STATES:
            return {}
        _validate_durable_context(context, Path(context_ref))
        if observe and turn_id:
            binding = dict(binding)
            binding["revision"] = int(binding["revision"]) + 1
            binding["last_observation"] = {
                "turn_id": turn_id,
                "event_name": event_name,
                "observed_at": now_utc(),
            }
            binding["updated_at"] = now_utc()
            atomic_write_json(binding_path(sejong_home, session_id, namespace), binding)
        context["_king_sejong_binding_epoch"] = binding["binding_epoch"]
        context["_king_sejong_binding_revision"] = binding["revision"]
        return context
    finally:
        lock.release()


def migrate_legacy_pointer(
    sejong_home: Path,
    *,
    before_materialize: Callable[[Path, dict[str, Any]], None] | None = None,
) -> Path:
    legacy_path = sejong_home / "state" / "active-context.json"
    if not legacy_path.exists():
        raise InvalidBinding(f"legacy active context does not exist: {legacy_path}")
    legacy_bytes = legacy_path.read_bytes()
    digest = hashlib.sha256(legacy_bytes).hexdigest()
    context_id: str | None = None
    context_ref: str | None = None
    context_materialized = False
    context_materialization_error: str | None = None
    repo_index_updated = False
    repo_index_error: str | None = None
    try:
        legacy = json.loads(legacy_bytes)
        if isinstance(legacy, dict):
            raw_context_id = legacy.get("active_context_id")
            context_id = raw_context_id if isinstance(raw_context_id, str) and raw_context_id else None
            run_id = legacy.get("run_id")
            repo_id = legacy.get("repo_id")
            repo_root = legacy.get("repo_root")
            repo_identities = legacy.get("repo_identities")
            path_components = (repo_id, run_id)
            safe_path_components = all(
                isinstance(value, str)
                and value not in {"", ".", ".."}
                and "/" not in value
                and "\\" not in value
                and "\0" not in value
                for value in path_components
            )
            usable_repo_identities = repo_identities is None or (
                isinstance(repo_identities, list)
                and all(isinstance(value, str) and value for value in repo_identities)
            )
            usable_context_metadata = (
                legacy.get("format") == "king-sejong.context/v0.1-draft"
                and context_id is not None
                and safe_path_components
                and isinstance(repo_root, str)
                and bool(repo_root)
                and "\0" not in repo_root
                and usable_repo_identities
                and legacy.get("context_status", "active") in {"active", "paused", "completed", "closed"}
                and isinstance(legacy.get("last_updated_at"), str)
                and bool(legacy.get("last_updated_at"))
            )
            if usable_context_metadata:
                materialized_context = legacy
                runs_root = (sejong_home / "runs").resolve()
                candidate = runs_root / repo_id / run_id / "king-sejong-context.json"
                try:
                    if not path_contains_or_equals(candidate, runs_root) or candidate.is_symlink():
                        raise InvalidBinding("legacy Context destination escapes the configured runs root")
                    _validate_durable_context(legacy, candidate)
                    if candidate.exists():
                        existing = json.loads(candidate.read_text(encoding="utf-8"))
                        identity_fields = ("active_context_id", "repo_id", "run_id")
                        if not isinstance(existing, dict) or any(
                            existing.get(field) != legacy.get(field) for field in identity_fields
                        ):
                            raise InvalidBinding("existing durable Context identity conflicts with legacy metadata")
                        _validate_durable_context(existing, candidate)
                        materialized_context = existing
                    else:
                        if before_materialize is not None:
                            before_materialize(candidate, legacy)
                        from sejong_context import (
                            ContextIdentityConflict,
                            ContextRevisionConflict,
                            save_context,
                        )

                        materialized_context = dict(legacy)
                        try:
                            save_context(
                                materialized_context,
                                expected_context_revision=0,
                                operation="materialize legacy Context",
                                sejong_home=sejong_home,
                                update_repo_index_after_commit=False,
                            )
                        except (ContextIdentityConflict, ContextRevisionConflict) as error:
                            raise InvalidBinding(str(error)) from error
                    context_ref = str(candidate.resolve())
                    context_materialized = True
                except (
                    InvalidBinding,
                    json.JSONDecodeError,
                    OSError,
                    TypeError,
                    UnicodeError,
                    ValueError,
                ) as error:
                    context_materialization_error = f"{type(error).__name__}: {error}"
                if context_materialized:
                    try:
                        update_repo_index(sejong_home, materialized_context, candidate)
                        repo_index_updated = True
                    except (
                        InvalidBinding,
                        RuntimeLockReleaseError,
                        RuntimeLockTimeout,
                        KeyError,
                        OSError,
                        TypeError,
                        UnicodeError,
                        ValueError,
                    ) as error:
                        repo_index_error = f"{type(error).__name__}: {error}"
    except (json.JSONDecodeError, UnicodeError):
        pass
    migration_path = sejong_home / "state" / "legacy-active-context-migration.json"
    atomic_write_json(
        migration_path,
        {
            "format": MIGRATION_FORMAT,
            "legacy_path": str(legacy_path.resolve()),
            "legacy_sha256": digest,
            "legacy_bytes_preserved": True,
            "automatic_injection_authority": False,
            "active_context_id": context_id,
            "context_ref": context_ref,
            "context_materialized": context_materialized,
            "context_materialization_error": context_materialization_error,
            "repo_index_updated": repo_index_updated,
            "repo_index_error": repo_index_error,
            "migrated_at": now_utc(),
        },
    )
    return migration_path
