#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


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
    "majority vote",
    "by majority",
    "consensus approves",
)
AMBIGUITY_REGISTER_FORMAT = "sejong.ambiguity-register/v0.1-draft"


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


def load_context(path: str | None) -> dict[str, Any]:
    context_path = resolve_context_path(path)
    if not context_path.exists():
        return {}
    return json.loads(context_path.read_text(encoding="utf-8"))


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
    summary = (
        "King Sejong active context: "
        f"active_context_id={context.get('active_context_id')}; "
        f"route_id={context.get('route_id')}; "
        f"current_surface={context.get('current_surface')}; "
        f"route_sequence={','.join(context.get('route_sequence', []))}; "
        f"pending_gates={','.join(context.get('pending_gates', [])) or 'none'}. "
        "Continue through Sejong lead routing until an explicit exit condition is met."
    )
    ambiguity_text = ambiguity_register_summary(context)
    if ambiguity_text:
        summary += " " + ambiguity_text
    return summary


def context_applies_to_cwd(context: dict[str, Any], payload: dict[str, Any]) -> bool:
    repo_root = context.get("repo_root")
    if not repo_root:
        return True
    cwd = Path(payload.get("cwd") or os.getcwd()).expanduser().resolve()
    root = Path(repo_root).expanduser().resolve()
    try:
        cwd.relative_to(root)
        return True
    except ValueError:
        return cwd == root


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


def flatten_tool_input(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_tool_input(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_tool_input(item) for item in value)
    return str(value)


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
        return Path(repo_root).expanduser() / path
    return Path.cwd() / path


def looks_like_ambiguity_register_ref(ref: str) -> bool:
    lowered = ref.lower()
    return "ambiguity" in lowered and lowered.endswith(".json")


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


def ambiguity_register_summary(context: dict[str, Any]) -> str:
    registers, broken_refs = load_ambiguity_registers(context)
    parts: list[str] = []
    for register in registers:
        metadata = register.get("metadata") or {}
        register_id = metadata.get("id") or "unknown"
        readiness = register.get("readiness_percent", "unknown")
        open_count = open_ambiguity_count(register)
        next_action = register.get("next_required_user_action") or "none"
        parts.append(
            "ambiguity_register="
            f"{register_id}; stage={register.get('stage_label') or register.get('stage_id')}; "
            f"readiness={readiness}%; open_ambiguities={open_count}; next_action={next_action}."
        )
    if broken_refs:
        parts.append("broken_ambiguity_register_refs=" + ",".join(broken_refs) + ".")
    return " ".join(parts)


def open_ambiguity_total(context: dict[str, Any]) -> int:
    registers, _ = load_ambiguity_registers(context)
    return sum(open_ambiguity_count(register) for register in registers)


def broken_ambiguity_register_refs(context: dict[str, Any]) -> list[str]:
    _, broken_refs = load_ambiguity_registers(context)
    return broken_refs


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
    if not touched:
        return {}
    if not route_sequence_satisfied(context):
        reason = (
            "King Sejong protected self-modification requires route evidence: "
            "Jiphyeonjeon -> Uigwe -> Seungjeongwon. "
            f"Touched protected paths: {', '.join(touched)}"
        )
        return deny_pre_tool(reason)
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
    return {}


def message_claims_forbidden_authority(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in FORBIDDEN_WORKER_AUTHORITY_TERMS)


def handle_subagent_stop(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("last_assistant_message") or ""
    if message_claims_forbidden_authority(message):
        return {
            "decision": "block",
            "reason": (
                "Subagent output must stay bounded. Return evidence, risks, or implementation notes only; "
                "Sejong lead owns gates, synthesis, and final verification."
            ),
        }
    if context:
        return hook_context("SubagentStop", "Return bounded evidence to the Sejong lead; do not approve gates.")
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
    if context:
        return hook_context(event_name, "Keep teammate messages bounded; return evidence to the Sejong lead.")
    return {}


def handle_stop(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if payload.get("stop_hook_active"):
        return {}
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
    open_count = open_ambiguity_total(context)
    if open_count:
        return {
            "decision": "block",
            "reason": f"Continue King Sejong execution: open King Sejong ambiguity remains: {open_count}",
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
    return hook_context("PreCompact", context_summary(context))


def handle_post_tool_use(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    touched = touched_protected_paths(context, payload)
    if touched:
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
        return {}
    if event_name == "UserPromptSubmit":
        return handle_user_prompt_submit(payload, context)
    if event_name in {"SessionStart", "PostCompact", "SubagentStart"}:
        return handle_session_context(event_name, context)
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
    context = load_context(args.context)
    return emit(dispatch(args.event_name, payload, context))


if __name__ == "__main__":
    raise SystemExit(main())
