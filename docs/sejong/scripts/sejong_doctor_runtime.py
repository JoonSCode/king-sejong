#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TypeAlias

from sejong_cleanup import bound_run_protection
from sejong_context import validate_context
from sejong_runtime_lock import DEFAULT_STALE_AFTER_SECONDS, read_lock_record, stale_lock_reason, value_as_str


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
TRUSTED_REPO_ROOT = SCRIPT_PATH.parents[3]

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str
    detail: str
    hint: str = ""


def sejong_home() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def read_json_object(path: Path) -> tuple[JsonObject | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, f"expected JSON object, got {type(data).__name__}"
    return {key: item if json_is_compatible(item) else str(item) for key, item in data.items() if isinstance(key, str)}, None


def json_is_compatible(value: JsonValue) -> bool:
    return isinstance(value, str | list | dict) or type(value) in {int, float, bool} or value is None


def load_hook_module() -> ModuleType:
    scripts_path = str(SEJONG_ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    import king_sejong_hooks

    return king_sejong_hooks


def run_context_paths(root: Path) -> list[Path]:
    runs_root = root / "runs"
    if not runs_root.exists():
        return []
    return sorted(runs_root.glob("*/*/king-sejong-context.json"))


def runtime_contexts(root: Path) -> list[tuple[Path, JsonObject]]:
    contexts: list[tuple[Path, JsonObject]] = []
    for path in run_context_paths(root):
        context, _ = read_json_object(path)
        if context is not None:
            contexts.append((path, context))
    return contexts


def context_label(context: JsonObject) -> str:
    return f"{context.get('active_context_id', '<unknown-context>')}/{context.get('run_id', '<unknown-run>')}"


def active_run_summaries(contexts: list[tuple[Path, JsonObject]]) -> list[str]:
    hooks = load_hook_module()
    summaries: list[str] = []
    for _, context in contexts:
        if not validate_context(context) and context.get("context_status", "active") == "active" and (
            context.get("pending_gates")
            or hooks.active_seungjeongwon_run_summaries(context)
            or hooks.open_ambiguity_total(context)
            or hooks.pending_question_obligation_total(context)
        ):
            summaries.append(context_label(context))
    return summaries


def active_runs_check(contexts: list[tuple[Path, JsonObject]]) -> Check:
    active_runs = active_run_summaries(contexts)
    if active_runs:
        return Check("multisession-active-runs", "warn", "active runtime runs: " + "; ".join(active_runs))
    return Check("multisession-active-runs", "ok", "no active runtime runs found")


def active_pointer_staleness_check(root: Path, _repo_root: Path, _contexts: list[tuple[Path, JsonObject]]) -> Check:
    active_path = root / "state" / "active-context.json"
    active_context, error = read_json_object(active_path)
    if active_context is None:
        status = "ok" if error == "missing" else "warn"
        return Check("active-pointer-staleness", status, f"legacy active pointer {error}: {active_path}")
    return Check(
        "active-pointer-staleness",
        "warn",
        "legacy active pointer is preserved but non-authoritative: "
        f"{context_label(active_context)}; automatic_injection_authority=false",
    )


def broken_ref_check(repo_root: Path, contexts: list[tuple[Path, JsonObject]]) -> Check:
    hooks = load_hook_module()
    failures: list[str] = []
    warnings: list[str] = []
    payload = {"cwd": str(repo_root)}
    for _, context in contexts:
        refs = (
            hooks.broken_ambiguity_register_refs(context)
            + hooks.broken_seungjeongwon_run_refs(context)
            + hooks.invalid_seungjeongwon_run_refs(context)
            + hooks.broken_continuity_capsule_refs(context)
            + hooks.invalid_continuity_capsule_refs(context)
        )
        if refs:
            target = failures if hooks.context_applies_to_cwd(context, payload) else warnings
            target.append(f"{context_label(context)}: {', '.join(refs)}")
    if failures:
        return Check("runtime-broken-refs", "fail", "broken runtime refs: " + "; ".join(failures))
    if warnings:
        return Check("runtime-broken-refs", "warn", "off-repo broken runtime refs: " + "; ".join(warnings))
    return Check("runtime-broken-refs", "ok", "no broken runtime refs found")


def lock_owner_summary(path: Path, record: JsonObject, reason: str | None) -> str:
    fields = [
        f"path={path}",
        f"lock_class={value_as_str(record.get('lock_class'), '<unknown>')}",
        f"owner_session_id={value_as_str(record.get('owner_session_id'), '<unknown>')}",
        f"owner_run_id={value_as_str(record.get('owner_run_id'), '<none>')}",
        f"owner_device_id={value_as_str(record.get('owner_device_id'), '<unknown>')}",
        f"operation={value_as_str(record.get('operation'), '<unknown>')}",
    ]
    if reason:
        fields.append(f"reason={reason}")
    return " ".join(fields)


def runtime_lock_check(root: Path) -> Check:
    lock_paths = sorted((root / "state" / "locks").glob("*.lock"))
    if not lock_paths:
        return Check("runtime-locks", "ok", "no runtime locks present")
    malformed: list[str] = []
    stuck: list[str] = []
    for path in lock_paths:
        record = read_lock_record(path)
        if record is None or record.get("format") == "malformed":
            malformed.append(str(path))
            continue
        threshold = record.get("stale_after_seconds")
        stale_after = threshold if type(threshold) is int or type(threshold) is float else DEFAULT_STALE_AFTER_SECONDS
        reason = stale_lock_reason(record, path, float(stale_after))
        if reason:
            stuck.append(lock_owner_summary(path, record, reason))
    if malformed:
        return Check("runtime-locks", "fail", "malformed runtime lock metadata: " + ", ".join(malformed))
    if stuck:
        return Check("runtime-locks", "warn", "stuck runtime locks: " + "; ".join(stuck))
    return Check("runtime-locks", "ok", f"runtime locks present but not stale: {len(lock_paths)}")


def cleanup_dry_run_check(contexts: list[tuple[Path, JsonObject]]) -> Check:
    retained: list[str] = []
    binding_failures: list[str] = []
    for context_path, context in contexts:
        protected, failures = bound_run_protection(context_path.parent)
        if protected:
            retained.append(context_label(context))
        binding_failures.extend(failures)
    if binding_failures:
        return Check(
            "runtime-cleanup-dry-run",
            "warn",
            "destructive cleanup would fail closed on invalid session binding state: "
            + "; ".join(binding_failures),
        )
    if retained:
        return Check("runtime-cleanup-dry-run", "ok", "would retain exactly bound active runs: " + "; ".join(retained))
    return Check("runtime-cleanup-dry-run", "ok", "no exactly bound active runs require cleanup retention")


def install_drift_check(repo_root: Path) -> Check:
    if repo_root.resolve() != TRUSTED_REPO_ROOT:
        return Check(
            "install-update-drift",
            "warn",
            "user-scope install drift not executed: repo root is not the trusted King Sejong source tree",
            f"Run from trusted source root: {TRUSTED_REPO_ROOT}",
        )
    try:
        result = subprocess.run(
            ["bash", str(TRUSTED_REPO_ROOT / "scripts/install-sejong.sh"), "--scope", "user", "--verify"],
            text=True,
            capture_output=True,
            timeout=10,
            cwd=str(TRUSTED_REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check("install-update-drift", "warn", f"could not inspect user-scope install drift: {exc}")
    if result.returncode == 0:
        return Check("install-update-drift", "ok", "user-scope install matches managed source")
    detail = (result.stderr or result.stdout).strip().splitlines()
    return Check("install-update-drift", "warn", "user-scope install drift detected: " + (detail[0] if detail else "verify failed"))


def multisession_checks(repo_root: Path) -> list[Check]:
    root = sejong_home()
    contexts = runtime_contexts(root)
    return [
        active_runs_check(contexts),
        active_pointer_staleness_check(root, repo_root, contexts),
        broken_ref_check(repo_root, contexts),
        runtime_lock_check(root),
        cleanup_dry_run_check(contexts),
        install_drift_check(repo_root),
    ]
