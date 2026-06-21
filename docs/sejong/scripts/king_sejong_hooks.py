#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from sejong_paths import path_contains_or_equals, resolve_path
from bounded_worker_brief import validate_bounded_worker_brief
from continuity_capsule import FORMAT as CONTINUITY_CAPSULE_FORMAT
from continuity_capsule import capsule_failures, capsule_projection
from seungjeongwon_run import checkpoint_failures, checkpoint_payload
from seungjeongwon_run import RUN_FORMAT as SEUNGJEONGWON_RUN_FORMAT
from seungjeongwon_run import format_run_summary as seungjeongwon_format_run_summary
from seungjeongwon_run import run_failures as seungjeongwon_run_failures


REQUIRED_CONTEXT_FIELDS = (
    "active_context_id",
    "repo_id",
    "repo_root",
    "run_id",
    "session_id",
    "route_id",
    "current_surface",
    "route_sequence",
    "required_route_sequence",
    "last_user_intent",
    "pending_gates",
    "protected_paths",
    "allowed_direct_change_types",
    "evidence_refs",
    "artifact_refs",
    "team_run_refs",
    "subagent_refs",
    "exit_conditions",
    "last_updated_at",
)
CONTEXT_LIST_FIELDS = (
    "route_sequence",
    "required_route_sequence",
    "pending_gates",
    "protected_paths",
    "allowed_direct_change_types",
    "evidence_refs",
    "artifact_refs",
    "team_run_refs",
    "subagent_refs",
    "exit_conditions",
)

EXIT_TERMS = (
    "exit sejong",
    "leave sejong",
    "normal codex",
    "stop using sejong",
    "세종 종료",
    "세종 그만",
    "일반 codex",
)

FORBIDDEN_WORKER_AUTHORITY_TERMS = (
    "approve the uigwe gate",
    "approved the uigwe gate",
    "uigwe gate approved",
    "gate approved",
    "final decision",
    "final synthesis",
    "final verification",
    "final verification complete",
    "completed final verification",
    "final completion",
    "majority vote",
    "by majority",
    "consensus approval",
    "consensus approves",
)
AMBIGUITY_REGISTER_FORMAT = "sejong.ambiguity-register/v0.1-draft"
UNRESOLVED_AMBIGUITY_STATUSES = {"open", "pending", "answered"}
PENDING_QUESTION_OBLIGATION_STATUSES = {"pending", "answered"}
UIGWE_LIVE_STAGE_IDS = {
    "intent_clarification",
    "design_clarification",
    "executor_handoff_contract",
}
UIGWE_PROMOTION_GATE = "uigwe_promotion_required"
SEUNGJEONGWON_RECEIPT_GATE = "seungjeongwon_receipt_required"
WRITE_LIKE_TOOL_NAMES = {
    "apply_patch",
    "edit",
    "multiedit",
    "write",
}
WRITE_LIKE_COMMAND_PATTERNS = (
    r"\*\*\* begin patch",
    r"(?:^|[;\n]|\|\||&&)\s*git\s+commit\b",
    r"(?:^|[;\n]|\|\||&&)\s*git\s+push\b",
    r"(?:^|[;\n]|\|\||&&)\s*sed\s+-i\b",
    r"(?:^|[;\n]|\|\||&&)\s*tee\s+",
    r"(?:^|[;\n]|\|\||&&)\s*cat\s+>",
    r"(?:^|[;\n]|\|\||&&)\s*cat\s+<<",
    r"(?:^|[;\n]|\|\||&&)\s*(?:echo|printf|cat)\b[\s\S]*\s>>?\s*",
    r"(?:^|[;\n]|\|\||&&)\s*(?:uv\s+run(?:\s+--with\s+\S+)*\s+python[0-9.]*|python[0-9.]*|python)\b[\s\S]*(?:open\s*\([^)]*,\s*['\"][wax+]|write_text\s*\(|write_bytes\s*\()",
    r"(?:^|[;\n]|\|\||&&)\s*(?:node|bun|deno)\b[\s\S]*(?:writefilesync\s*\(|appendfilesync\s*\(|createwritestream\s*\()",
    r"(?:^|[;\n]|\|\||&&)\s*ruby\b[\s\S]*(?:file\.write\s*\(|file\.open\s*\([^)]*,\s*['\"][wa])",
    r"(?:^|[;\n]|\|\||&&)\s*perl\b[\s\S]*(?:open\s+[^;\n]*,\s*['\"]?>{1,2}|sysopen\s*\([^)]*(?:o_wronly|o_creat|o_append))",
    r"(?:^|[;\n]|\|\||&&)\s*php\b[\s\S]*(?:file_put_contents\s*\(|fopen\s*\([^)]*,\s*['\"][wax+])",
    r"(?:^|[;\n]|\|\||&&)\s*awk\b[\s\S]*\s>>?\s*",
    r"(?:^|[;\n]|\|\||&&)\s*dd\b[\s\S]*\bof=",
    r"(?:^|[;\n]|\|\||&&)\s*install\b\s+",
    r"(?:^|[;\n]|\|\||&&)\s*rsync\b\s+",
    r"(?:^|[;\n]|\|\||&&)\s*mv\s+",
    r"(?:^|[;\n]|\|\||&&)\s*cp\s+",
    r"(?:^|[;\n]|\|\||&&)\s*rm\s+",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reference King Sejong Codex hook guardrails.")
    parser.add_argument("event_name", help="Codex hook event name, such as UserPromptSubmit or PreToolUse.")
    parser.add_argument("--context", help="Path to a King Sejong active context checkpoint JSON file.")
    return parser.parse_args()


def load_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def load_context_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def iter_run_context_paths() -> list[Path]:
    runs_root = sejong_root() / "runs"
    if not runs_root.exists():
        return []
    return list(runs_root.glob("*/*/king-sejong-context.json"))


def context_is_well_formed(context: dict[str, Any]) -> bool:
    if not context:
        return False
    if context.get("format") and context.get("format") != "king-sejong.context/v0.1-draft":
        return False
    if missing_context_fields(context):
        return False
    for field in CONTEXT_LIST_FIELDS:
        value = context.get(field)
        if not isinstance(value, list):
            return False
        if any(not isinstance(item, str) or not item for item in value):
            return False
    return True


def newest_matching_repo_context(payload: dict[str, Any]) -> dict[str, Any]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for context_path in iter_run_context_paths():
        context = load_context_file(context_path)
        if not context_is_well_formed(context):
            continue
        if not context_applies_to_cwd(context, payload):
            continue
        try:
            mtime = context_path.stat().st_mtime
        except OSError:
            mtime = 0
        candidates.append((mtime, context))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def load_context(path: str | None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    context_path = resolve_context_path(path)
    if not context_path.exists():
        if not path and payload:
            return newest_matching_repo_context(payload)
        return {}
    active_context = load_context_file(context_path)
    if path or not payload or context_applies_to_cwd(active_context, payload):
        return active_context
    return newest_matching_repo_context(payload) or active_context


def sejong_root() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def resolve_context_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser()
    if os.environ.get("SEJONG_ACTIVE_CONTEXT"):
        return Path(os.environ["SEJONG_ACTIVE_CONTEXT"]).expanduser()
    return sejong_root() / "state" / "active-context.json"


def emit(payload: dict[str, Any]) -> int:
    if payload:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def hook_context(event_name: str, text: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }


def context_summary(context: dict[str, Any]) -> str:
    repo_root = resolve_path(context.get("repo_root", ""))
    summary = (
        "King Sejong active context: "
        f"active_context_id={context.get('active_context_id')}; "
        f"route_id={context.get('route_id')}; "
        f"repo_root={repo_root}; "
        f"objective_id={context.get('objective_id') or 'none'}; "
        f"task_class={context.get('task_class') or 'none'}; "
        f"projection_profile={context.get('projection_profile') or 'default'}; "
        f"current_surface={context.get('current_surface')}; "
        f"route_sequence={','.join(context.get('route_sequence', []))}; "
        f"pending_gates={','.join(context.get('pending_gates', [])) or 'none'}; "
        f"objective_refs={','.join(context.get('objective_refs', [])) or 'none'}; "
        f"last_user_intent={context.get('last_user_intent')}. "
        "Continue through Sejong lead routing until an explicit exit condition is met."
    )
    continuity_text = continuity_capsule_summary(context)
    if continuity_text:
        summary += " " + continuity_text
    ambiguity_text = ambiguity_register_summary(context)
    if ambiguity_text:
        summary += " " + ambiguity_text
    active_runs = active_seungjeongwon_run_summaries(context)
    if active_runs:
        summary += " active_seungjeongwon_runs=" + ";".join(active_runs) + "."
    if pending_uigwe_promotion_unsatisfied(context):
        summary += (
            " uigwe_promotion_required=true; research or council output is not final; "
            "enter Uigwe or ask the user to convert the request to research-only."
        )
    return summary


def worker_payload_role(payload: dict[str, Any]) -> str:
    return str(
        payload.get("worker_role")
        or payload.get("role")
        or payload.get("agent_type")
        or payload.get("teammate_name")
        or "bounded-worker"
    )


def worker_payload_scope(payload: dict[str, Any]) -> str:
    return str(payload.get("worker_scope") or payload.get("scope") or payload.get("task") or "assigned scope only")


def worker_payload_objective(context: dict[str, Any], payload: dict[str, Any]) -> str:
    return str(
        payload.get("worker_objective")
        or payload.get("objective")
        or payload.get("task")
        or context.get("objective_id")
        or "return bounded evidence to the Sejong lead"
    )


def worker_payload_write_scope(payload: dict[str, Any]) -> list[str]:
    value = payload.get("write_scope") or payload.get("allowed_file_scope") or payload.get("worker_write_scope")
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return ["none"]


def bounded_worker_contract_summary(context: dict[str, Any], payload: dict[str, Any]) -> str:
    refs = (
        context.get("source_of_truth_refs")
        or context.get("artifact_refs")
        or context.get("evidence_refs")
        or context.get("objective_refs")
        or []
    )
    if not refs:
        refs = ["active-context"]
    allowed_outputs = [
        "bounded evidence",
        "risks",
        "implementation notes",
        "verification observations",
        "blockers",
    ]
    forbidden_claims = [
        "Uigwe gate approval",
        "final synthesis",
        "final verification",
        "majority-vote authority",
        "consensus approval",
        "scope widening",
    ]
    return (
        "Bounded worker contract: "
        f"objective={worker_payload_objective(context, payload)}; "
        f"worker_role={worker_payload_role(payload)}; "
        f"worker_scope={worker_payload_scope(payload)}; "
        f"source_of_truth_refs={','.join(refs) or 'none'}; "
        f"allowed_outputs={','.join(allowed_outputs)}; "
        f"forbidden_claims={','.join(forbidden_claims)}; "
        f"write_scope={','.join(worker_payload_write_scope(payload))}; "
        f"evidence_refs={','.join(refs)}; "
        "return_format=bounded brief with evidence refs, confidence, residual risk, and blocker_or_next_step; "
        "stop_condition=return to the Sejong lead after the assigned output or blocker."
    )


def handle_subagent_start(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not context:
        return {}
    return hook_context("SubagentStart", context_summary(context) + " " + bounded_worker_contract_summary(context, payload))


def context_applies_to_cwd(context: dict[str, Any], payload: dict[str, Any]) -> bool:
    repo_root = context.get("repo_root")
    if not repo_root:
        return True
    cwd = resolve_path(payload.get("cwd") or os.getcwd())
    root = resolve_path(repo_root)
    return path_contains_or_equals(cwd, root)


def repo_mismatch_summary(context: dict[str, Any], payload: dict[str, Any]) -> str:
    cwd = resolve_path(payload.get("cwd") or os.getcwd())
    repo_root = resolve_path(context.get("repo_root", ""))
    return (
        "King Sejong active context repo_mismatch=true; "
        f"active_context_id={context.get('active_context_id')}; "
        f"active_repo_root={repo_root}; current_cwd={cwd}. "
        "This context is not applied to the current workspace; refresh the active context "
        "or start a repo-scoped Sejong context before treating follow-up prompts as the same workflow."
    )


def is_explicit_exit(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(term in lowered for term in EXIT_TERMS)


def route_sequence_satisfied(context: dict[str, Any]) -> bool:
    required = context.get("required_route_sequence") or []
    observed = context.get("route_sequence") or []
    if not required:
        return False

    index = 0
    for route in observed:
        if index < len(required) and route == required[index]:
            index += 1
    return index == len(required)


def route_entered(context: dict[str, Any], surface: str) -> bool:
    return surface in (context.get("route_sequence") or [])


def has_pending_uigwe_promotion(context: dict[str, Any]) -> bool:
    return UIGWE_PROMOTION_GATE in (context.get("pending_gates") or [])


def pending_uigwe_promotion_unsatisfied(context: dict[str, Any]) -> bool:
    return has_pending_uigwe_promotion(context) and not route_entered(context, "uigwe")


def has_pending_seungjeongwon_receipt(context: dict[str, Any]) -> bool:
    return SEUNGJEONGWON_RECEIPT_GATE in (context.get("pending_gates") or [])


def required_route_needs_seungjeongwon_receipt(context: dict[str, Any]) -> bool:
    return "seungjeongwon" in (context.get("required_route_sequence") or [])


def has_native_goal_unavailable_receipt(context: dict[str, Any]) -> bool:
    refs = (context.get("artifact_refs") or []) + (context.get("evidence_refs") or [])
    return any("native_goal_unavailable" in ref for ref in refs if isinstance(ref, str))


def has_valid_seungjeongwon_receipt(context: dict[str, Any]) -> bool:
    if context.get("current_surface") != "seungjeongwon" or not route_entered(context, "seungjeongwon"):
        return False
    runs, broken_refs, invalid_refs = load_seungjeongwon_runs(context)
    if broken_refs or invalid_refs:
        return False
    return bool(runs) or has_native_goal_unavailable_receipt(context)


def pending_seungjeongwon_receipt_unsatisfied(context: dict[str, Any]) -> bool:
    return has_pending_seungjeongwon_receipt(context) and not has_valid_seungjeongwon_receipt(context)


def flatten_tool_input(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_tool_input(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_tool_input(item) for item in value)
    return str(value)


def tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "").lower()


def is_write_like_tool_call(payload: dict[str, Any]) -> bool:
    name = tool_name(payload)
    if name in WRITE_LIKE_TOOL_NAMES:
        return True
    haystack = flatten_tool_input(payload.get("tool_input", "")).lower()
    return any(re.search(pattern, haystack) for pattern in WRITE_LIKE_COMMAND_PATTERNS)


def touched_protected_paths(context: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    haystack = flatten_tool_input(payload.get("tool_input", ""))
    protected = context.get("protected_paths") or []
    return [path for path in protected if path and path in haystack]


def resolve_artifact_ref(ref: str, context: dict[str, Any]) -> Path:
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path
    repo_root = context.get("repo_root")
    if repo_root:
        return resolve_path(repo_root) / path
    return Path.cwd() / path


def looks_like_ambiguity_register_ref(ref: str) -> bool:
    lowered = ref.lower()
    return "ambiguity" in lowered and lowered.endswith(".json")


def looks_like_seungjeongwon_run_ref(ref: str) -> bool:
    lowered = ref.lower()
    return "seungjeongwon-run" in lowered and lowered.endswith(".json")


def looks_like_continuity_capsule_ref(ref: str) -> bool:
    lowered = ref.lower()
    return "continuity-capsule" in lowered and lowered.endswith(".json")


def load_ambiguity_registers(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    registers: list[dict[str, Any]] = []
    broken_refs: list[str] = []
    for ref in context.get("artifact_refs") or []:
        path = resolve_artifact_ref(ref, context)
        if not path.exists():
            if looks_like_ambiguity_register_ref(ref):
                broken_refs.append(str(path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            if looks_like_ambiguity_register_ref(ref):
                broken_refs.append(str(path))
            continue
        if data.get("format") == AMBIGUITY_REGISTER_FORMAT:
            registers.append(data)
    return registers, broken_refs


def open_ambiguity_count(register: dict[str, Any]) -> int:
    ambiguities = register.get("ambiguities") or []
    if isinstance(ambiguities, list):
        return sum(1 for item in ambiguities if isinstance(item, dict) and item.get("status") == "open")
    blocking_count = register.get("blocking_count")
    return blocking_count if isinstance(blocking_count, int) and blocking_count > 0 else 0


def pending_question_obligation_count(register: dict[str, Any]) -> int:
    ambiguities = register.get("ambiguities") or []
    if not isinstance(ambiguities, list):
        return 0
    return sum(
        1
        for item in ambiguities
        if isinstance(item, dict)
        and item.get("status") in PENDING_QUESTION_OBLIGATION_STATUSES
        and item.get("blocking", True) is not False
    )


def unresolved_ambiguity_count(register: dict[str, Any]) -> int:
    ambiguities = register.get("ambiguities") or []
    if isinstance(ambiguities, list):
        return sum(
            1
            for item in ambiguities
            if isinstance(item, dict)
            and item.get("status") in UNRESOLVED_AMBIGUITY_STATUSES
            and item.get("blocking", True) is not False
        )
    blocking_count = register.get("blocking_count")
    return blocking_count if isinstance(blocking_count, int) and blocking_count > 0 else 0


def register_readiness_percent(register: dict[str, Any]) -> int | None:
    readiness = register.get("readiness_percent")
    if isinstance(readiness, int):
        return readiness
    return None


def uigwe_live_stage_incomplete_registers(context: dict[str, Any]) -> list[dict[str, Any]]:
    registers, _ = load_ambiguity_registers(context)
    incomplete: list[dict[str, Any]] = []
    for register in registers:
        if register.get("stage_id") not in UIGWE_LIVE_STAGE_IDS:
            continue
        readiness = register_readiness_percent(register)
        if unresolved_ambiguity_count(register) > 0 or readiness is None or readiness < 100:
            incomplete.append(register)
    return incomplete


def runtime_clarification_artifact_update(payload: dict[str, Any]) -> bool:
    haystack = flatten_tool_input(payload.get("tool_input", "")).lower()
    return any(
        marker in haystack
        for marker in (
            "--write-register",
            "ambiguity-register",
            AMBIGUITY_REGISTER_FORMAT,
            "king-sejong-context",
        )
    )


def ambiguity_register_summary(context: dict[str, Any]) -> str:
    registers, broken_refs = load_ambiguity_registers(context)
    parts: list[str] = []
    for register in registers:
        metadata = register.get("metadata") or {}
        register_id = metadata.get("id") or "unknown"
        readiness = register.get("readiness_percent", "unknown")
        open_count = open_ambiguity_count(register)
        pending_count = pending_question_obligation_count(register)
        next_action = register.get("next_required_user_action") or "none"
        parts.append(
            "ambiguity_register="
            f"{register_id}; stage={register.get('stage_label') or register.get('stage_id')}; "
            f"readiness={readiness}%; open_ambiguities={open_count}; "
            f"pending_question_obligations={pending_count}; next_action={next_action}."
        )
    if broken_refs:
        parts.append("broken_ambiguity_register_refs=" + ",".join(broken_refs) + ".")
    return " ".join(parts)


def load_continuity_capsules(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    capsules: list[dict[str, Any]] = []
    broken_refs: list[str] = []
    invalid_refs: list[str] = []
    for ref in context.get("artifact_refs") or []:
        path = resolve_artifact_ref(ref, context)
        if not path.exists():
            if looks_like_continuity_capsule_ref(ref):
                broken_refs.append(str(path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            if looks_like_continuity_capsule_ref(ref):
                broken_refs.append(str(path))
            continue
        if data.get("format") != CONTINUITY_CAPSULE_FORMAT:
            continue
        failures = capsule_failures(data)
        if failures:
            invalid_refs.append(f"{path}: {'; '.join(failures)}")
        capsules.append(data)
    return capsules, broken_refs, invalid_refs


def continuity_capsule_summary(context: dict[str, Any]) -> str:
    capsules, broken_refs, invalid_refs = load_continuity_capsules(context)
    parts: list[str] = []
    preferred_profile = context.get("projection_profile")
    for capsule in capsules:
        if capsule_failures(capsule):
            continue
        parts.append(capsule_projection(capsule, preferred_profile))
    if broken_refs:
        parts.append("broken_continuity_capsule_refs=" + ",".join(broken_refs) + ".")
    if invalid_refs:
        parts.append("invalid_continuity_capsule_refs=" + ",".join(invalid_refs) + ".")
    return " ".join(parts)


def broken_continuity_capsule_refs(context: dict[str, Any]) -> list[str]:
    _, broken_refs, _ = load_continuity_capsules(context)
    return broken_refs


def invalid_continuity_capsule_refs(context: dict[str, Any]) -> list[str]:
    _, _, invalid_refs = load_continuity_capsules(context)
    return invalid_refs


def open_ambiguity_total(context: dict[str, Any]) -> int:
    registers, _ = load_ambiguity_registers(context)
    return sum(open_ambiguity_count(register) for register in registers)


def pending_question_obligation_total(context: dict[str, Any]) -> int:
    registers, _ = load_ambiguity_registers(context)
    return sum(pending_question_obligation_count(register) for register in registers)


def broken_ambiguity_register_refs(context: dict[str, Any]) -> list[str]:
    _, broken_refs = load_ambiguity_registers(context)
    return broken_refs


def load_seungjeongwon_run_entries(context: dict[str, Any]) -> tuple[list[tuple[Path, dict[str, Any]]], list[str], list[str]]:
    entries: list[tuple[Path, dict[str, Any]]] = []
    broken_refs: list[str] = []
    invalid_refs: list[str] = []
    for ref in context.get("artifact_refs") or []:
        path = resolve_artifact_ref(ref, context)
        if not path.exists():
            if looks_like_seungjeongwon_run_ref(ref):
                broken_refs.append(str(path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            if looks_like_seungjeongwon_run_ref(ref):
                broken_refs.append(str(path))
            continue
        if data.get("format") != SEUNGJEONGWON_RUN_FORMAT:
            continue
        failures = seungjeongwon_run_failures(data)
        if failures:
            invalid_refs.append(f"{path}: {'; '.join(failures)}")
        entries.append((path, data))
    return entries, broken_refs, invalid_refs


def load_seungjeongwon_runs(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    entries, broken_refs, invalid_refs = load_seungjeongwon_run_entries(context)
    return [data for _, data in entries], broken_refs, invalid_refs


def checkpoint_path_for_run(context: dict[str, Any], run_path: Path, run_data: dict[str, Any]) -> Path:
    repo_id = context.get("repo_id") or "unknown-repo"
    context_run_id = context.get("run_id") or "unknown-run"
    run_id = run_data.get("run_id") or run_path.stem
    return sejong_root() / "runs" / str(repo_id) / str(context_run_id) / f"{run_id}.seungjeongwon-checkpoint.json"


def write_precompact_seungjeongwon_checkpoints(context: dict[str, Any]) -> tuple[list[str], list[str]]:
    entries, broken_refs, invalid_refs = load_seungjeongwon_run_entries(context)
    failures = list(broken_refs) + list(invalid_refs)
    if failures:
        return [], failures
    written: list[str] = []
    for run_path, run_data in entries:
        output_path = checkpoint_path_for_run(context, run_path, run_data)
        args = argparse.Namespace(
            checkpoint_id=f"checkpoint-{run_data.get('run_id')}-{context.get('active_context_id')}",
            context_id=context.get("active_context_id"),
            objective_id=context.get("objective_id"),
        )
        payload = checkpoint_payload(run_data, run_path, args)
        checkpoint_errors = checkpoint_failures(payload)
        if checkpoint_errors:
            failures.append(f"{output_path}: {'; '.join(checkpoint_errors)}")
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(str(output_path))
    return written, failures


def active_seungjeongwon_run_summaries(context: dict[str, Any]) -> list[str]:
    runs, _, _ = load_seungjeongwon_runs(context)
    summaries: list[str] = []
    for run in runs:
        if run.get("status") == "active":
            summaries.append(seungjeongwon_format_run_summary(run))
    return summaries


def broken_seungjeongwon_run_refs(context: dict[str, Any]) -> list[str]:
    _, broken_refs, _ = load_seungjeongwon_runs(context)
    return broken_refs


def invalid_seungjeongwon_run_refs(context: dict[str, Any]) -> list[str]:
    _, _, invalid_refs = load_seungjeongwon_runs(context)
    return invalid_refs


def deny_pre_tool(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def deny_permission(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "deny",
                "message": reason,
            },
        }
    }


def handle_user_prompt_submit(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt", "")
    if not context or is_explicit_exit(prompt):
        return {}
    return hook_context("UserPromptSubmit", context_summary(context))


def handle_session_context(event_name: str, context: dict[str, Any]) -> dict[str, Any]:
    if not context:
        return {}
    return hook_context(event_name, context_summary(context))


def handle_pre_tool_use(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    touched = touched_protected_paths(context, payload)
    is_write_like = is_write_like_tool_call(payload)
    if touched and is_write_like and not route_sequence_satisfied(context):
        reason = (
            "King Sejong protected self-modification requires route evidence: "
            "Jiphyeonjeon -> Uigwe -> Seungjeongwon. "
            f"Touched protected paths: {', '.join(touched)}"
        )
        return deny_pre_tool(reason)
    if pending_uigwe_promotion_unsatisfied(context) and is_write_like:
        return deny_pre_tool(
            "King Sejong research-to-Uigwe gate is pending. "
            "Research or council output must enter Uigwe before write-like execution, "
            "unless the user explicitly converts the request to research-only."
        )
    if pending_seungjeongwon_receipt_unsatisfied(context) and is_write_like:
        return deny_pre_tool(
            "King Sejong Seungjeongwon execution receipt is required before write-like execution. "
            "Enter Seungjeongwon, publish the execution board, and attach a valid "
            "sejong.seungjeongwon-run/v0.1-draft artifact before product-code edits."
        )
    incomplete_uigwe_registers = uigwe_live_stage_incomplete_registers(context)
    if (
        context.get("current_surface") == "uigwe"
        and incomplete_uigwe_registers
        and is_write_like
        and not runtime_clarification_artifact_update(payload)
    ):
        labels = [
            str(register.get("stage_label") or register.get("stage_id"))
            for register in incomplete_uigwe_registers
        ]
        return deny_pre_tool(
            "King Sejong Uigwe live-stage obligation remains unresolved. "
            "Resolve the active stage to 100% readiness or record an explicit user waiver "
            "before write-like execution. Active stages: " + ", ".join(labels)
        )
    if not touched:
        return {}
    return hook_context(
        "PreToolUse",
        "Protected King Sejong path touched after required route evidence; keep verification evidence before completion.",
    )


def handle_permission_request(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    touched = touched_protected_paths(context, payload)
    if touched and not route_sequence_satisfied(context):
        return deny_permission(
            "King Sejong protected self-modification requires Jiphyeonjeon -> Uigwe -> Seungjeongwon route evidence."
        )
    if pending_uigwe_promotion_unsatisfied(context) and is_write_like_tool_call(payload):
        return deny_permission(
            "King Sejong research-to-Uigwe gate is pending; enter Uigwe before write-like execution."
        )
    if pending_seungjeongwon_receipt_unsatisfied(context) and is_write_like_tool_call(payload):
        return deny_permission(
            "King Sejong Seungjeongwon execution receipt is required before write-like execution."
        )
    return {}


def message_claims_forbidden_authority(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in FORBIDDEN_WORKER_AUTHORITY_TERMS)


def fenced_json_blocks(message: str) -> list[str]:
    return re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", message, flags=re.IGNORECASE | re.DOTALL)


def parse_json_object(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def bounded_worker_brief_from_message(message: str) -> tuple[dict[str, Any] | None, str | None]:
    stripped = message.strip()
    if not stripped:
        return None, "missing bounded worker brief JSON"
    candidates = fenced_json_blocks(stripped)
    if not candidates:
        candidates.append(stripped)
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first >= 0 and last > first:
        candidates.append(stripped[first : last + 1])
    for candidate in candidates:
        data = parse_json_object(candidate.strip())
        if data is not None:
            return data, None
    return None, "missing parseable bounded worker brief JSON"


def subagent_expected_source_refs(context: dict[str, Any]) -> list[str]:
    refs = context.get("source_of_truth_refs") or []
    return [str(ref) for ref in refs if isinstance(ref, str) and ref]


def handle_subagent_stop(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("last_assistant_message") or ""
    if context:
        brief, parse_failure = bounded_worker_brief_from_message(message)
        if parse_failure:
            if message_claims_forbidden_authority(message):
                return {
                    "decision": "block",
                    "reason": (
                        "Subagent output must stay bounded. Return evidence, risks, or implementation notes only; "
                        "Sejong lead owns gates, synthesis, and final verification."
                    ),
                }
            return {
                "decision": "block",
                "reason": (
                    "Subagent output must return a JSON bounded worker brief with objective, role, "
                    "source refs, allowed outputs, forbidden claims, write scope, stop condition, "
                    f"and evidence refs: {parse_failure}."
                ),
            }
        failures = validate_bounded_worker_brief(
            brief or {},
            expected_source_of_truth_refs=subagent_expected_source_refs(context),
            label="subagent final bounded worker brief",
        )
        if failures:
            return {
                "decision": "block",
                "reason": "Invalid subagent bounded worker brief: " + "; ".join(failures),
            }
        return hook_context("SubagentStop", "Return bounded evidence to the Sejong lead; do not approve gates.")
    if message_claims_forbidden_authority(message):
        return {
            "decision": "block",
            "reason": (
                "Subagent output must stay bounded. Return evidence, risks, or implementation notes only; "
                "Sejong lead owns gates, synthesis, and final verification."
            ),
        }
    return {}


def handle_team_worker_event(event_name: str, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    message = json.dumps(payload, sort_keys=True)
    if message_claims_forbidden_authority(message):
        return {
            "decision": "block",
            "reason": (
                f"{event_name} must stay within King Sejong worker authority. "
                "Peer messages and task state are evidence only; Sejong lead owns gates, synthesis, and final verification."
            ),
        }
    if event_name == "TaskCreated" and context:
        return hook_context(event_name, bounded_worker_contract_summary(context, payload))
    if context:
        return hook_context(event_name, "Keep teammate messages bounded; return evidence to the Sejong lead.")
    return {}


def handle_stop(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if payload.get("stop_hook_active"):
        return {}
    if pending_uigwe_promotion_unsatisfied(context):
        return {
            "decision": "block",
            "reason": (
                "Continue King Sejong execution: uigwe_promotion_required remains pending. "
                "Research-for-decision must enter Uigwe or be explicitly converted to research-only."
            ),
        }
    if pending_seungjeongwon_receipt_unsatisfied(context):
        return {
            "decision": "block",
            "reason": (
                "Continue King Sejong execution: seungjeongwon_receipt_required remains pending. "
                "Goal-bearing execution needs a valid Seungjeongwon receipt before completion."
            ),
        }
    pending = context.get("pending_gates") or []
    if pending:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: pending King Sejong gates remain: " + ", ".join(pending),
        }
    broken_refs = broken_ambiguity_register_refs(context)
    if broken_refs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: broken King Sejong ambiguity register refs: "
            + ", ".join(broken_refs),
        }
    broken_run_refs = broken_seungjeongwon_run_refs(context)
    if broken_run_refs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: broken Seungjeongwon run refs: "
            + ", ".join(broken_run_refs),
        }
    invalid_run_refs = invalid_seungjeongwon_run_refs(context)
    if invalid_run_refs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: invalid Seungjeongwon run refs: "
            + ", ".join(invalid_run_refs),
        }
    broken_capsule_refs = broken_continuity_capsule_refs(context)
    if broken_capsule_refs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: broken continuity capsule refs: "
            + ", ".join(broken_capsule_refs),
        }
    invalid_capsule_refs = invalid_continuity_capsule_refs(context)
    if invalid_capsule_refs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: invalid continuity capsule refs: "
            + ", ".join(invalid_capsule_refs),
        }
    active_runs = active_seungjeongwon_run_summaries(context)
    if active_runs:
        return {
            "decision": "block",
            "reason": "Continue King Sejong execution: active Seungjeongwon run remains: "
            + ", ".join(active_runs),
        }
    open_count = open_ambiguity_total(context)
    if open_count:
        return {
            "decision": "block",
            "reason": f"Continue King Sejong execution: open King Sejong ambiguity remains: {open_count}",
        }
    pending_questions = pending_question_obligation_total(context)
    if pending_questions:
        return {
            "decision": "block",
            "reason": (
                "Continue King Sejong execution: pending King Sejong question obligations remain: "
                f"{pending_questions}"
            ),
        }
    return {}


def missing_context_fields(context: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_CONTEXT_FIELDS if field not in context or context[field] is None]


def handle_precompact(context: dict[str, Any]) -> dict[str, Any]:
    missing = missing_context_fields(context)
    if missing:
        return {
            "continue": False,
            "stopReason": "missing checkpoint fields: " + ", ".join(missing),
            "systemMessage": "King Sejong active context checkpoint is incomplete before compaction.",
        }
    broken_refs = broken_ambiguity_register_refs(context)
    if broken_refs:
        return {
            "continue": False,
            "stopReason": "broken ambiguity register refs: " + ", ".join(broken_refs),
            "systemMessage": "King Sejong ambiguity register references must be readable before compaction.",
        }
    broken_run_refs = broken_seungjeongwon_run_refs(context)
    if broken_run_refs:
        return {
            "continue": False,
            "stopReason": "broken Seungjeongwon run refs: " + ", ".join(broken_run_refs),
            "systemMessage": "King Sejong Seungjeongwon run references must be readable before compaction.",
        }
    invalid_run_refs = invalid_seungjeongwon_run_refs(context)
    if invalid_run_refs:
        return {
            "continue": False,
            "stopReason": "invalid Seungjeongwon run refs: " + ", ".join(invalid_run_refs),
            "systemMessage": "King Sejong Seungjeongwon run artifacts must validate before compaction.",
        }
    checkpoint_refs, checkpoint_failures = write_precompact_seungjeongwon_checkpoints(context)
    if checkpoint_failures:
        return {
            "continue": False,
            "stopReason": "failed Seungjeongwon checkpoint creation: " + ", ".join(checkpoint_failures),
            "systemMessage": "King Sejong Seungjeongwon run checkpoints must be writable before compaction.",
        }
    broken_capsule_refs = broken_continuity_capsule_refs(context)
    if broken_capsule_refs:
        return {
            "continue": False,
            "stopReason": "broken continuity capsule refs: " + ", ".join(broken_capsule_refs),
            "systemMessage": "King Sejong continuity capsule references must be readable before compaction.",
        }
    invalid_capsule_refs = invalid_continuity_capsule_refs(context)
    if invalid_capsule_refs:
        return {
            "continue": False,
            "stopReason": "invalid continuity capsule refs: " + ", ".join(invalid_capsule_refs),
            "systemMessage": "King Sejong continuity capsule artifacts must validate before compaction.",
        }
    output = hook_context("PreCompact", context_summary(context))
    if checkpoint_refs:
        output["hookSpecificOutput"]["additionalContext"] += (
            " seungjeongwon_checkpoints_created=" + ",".join(checkpoint_refs) + "."
        )
    return output


def handle_post_tool_use(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    touched = touched_protected_paths(context, payload)
    if touched and is_write_like_tool_call(payload):
        return {
            "decision": "block",
            "reason": "Record verification evidence for protected King Sejong path changes before continuing.",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Protected paths touched: " + ", ".join(touched),
            },
        }
    return {}


def dispatch(event_name: str, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if context and not context_applies_to_cwd(context, payload):
        if event_name == "UserPromptSubmit" and is_explicit_exit(payload.get("prompt", "")):
            return {}
        if event_name in {"UserPromptSubmit", "SessionStart", "PostCompact"}:
            return hook_context(event_name, repo_mismatch_summary(context, payload))
        return {}
    if event_name == "UserPromptSubmit":
        return handle_user_prompt_submit(payload, context)
    if event_name in {"SessionStart", "PostCompact"}:
        return handle_session_context(event_name, context)
    if event_name == "SubagentStart":
        return handle_subagent_start(payload, context)
    if event_name == "PreToolUse":
        return handle_pre_tool_use(payload, context)
    if event_name == "PermissionRequest":
        return handle_permission_request(payload, context)
    if event_name == "PostToolUse":
        return handle_post_tool_use(payload, context)
    if event_name == "SubagentStop":
        return handle_subagent_stop(payload, context)
    if event_name in {"TaskCreated", "TaskCompleted", "TeammateIdle"}:
        return handle_team_worker_event(event_name, payload, context)
    if event_name == "Stop":
        return handle_stop(payload, context)
    if event_name == "PreCompact":
        return handle_precompact(context)
    return {}


def main() -> int:
    args = parse_args()
    payload = load_stdin_json()
    context = load_context(args.context, payload)
    return emit(dispatch(args.event_name, payload, context))


if __name__ == "__main__":
    raise SystemExit(main())
