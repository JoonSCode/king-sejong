#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import resolve_path


RUN_FORMAT = "sejong.seungjeongwon-run/v0.1-draft"
CHECKPOINT_FORMAT = "sejong.seungjeongwon-checkpoint/v0.1-draft"
RESUME_FORMAT = "sejong.seungjeongwon-resume/v0.1-draft"
REPLAY_FORMAT = "sejong.seungjeongwon-replay/v0.1-draft"
STATUSES = {"active", "completed", "blocked", "invalidated", "failed"}
OPEN_TODO_STATUSES = {"pending", "in_progress"}
CLOSED_TODO_STATUSES = {"completed", "blocked", "invalidated", "replaced"}
TODO_STATUSES = OPEN_TODO_STATUSES | CLOSED_TODO_STATUSES
DEFAULT_GUARDRAIL_THRESHOLD = 0.98
DEFAULT_COVERAGE_THRESHOLD = 1.0
PROVENANCE_REQUIRED_FIELDS = (
    "created_by",
    "source_repo",
    "source_commit",
    "skill_version",
    "host",
    "model",
    "generated_at",
    "input_refs",
    "verification_refs",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_todo(value: str) -> dict[str, Any]:
    parts = value.split("|", 3)
    if len(parts) != 4 or not all(parts):
        raise argparse.ArgumentTypeError("todo must be todo_id|description|done_criteria|verification_method")
    return {
        "todo_id": parts[0],
        "description": parts[1],
        "done_criteria": parts[2],
        "verification_method": parts[3],
        "guardrail_scores": {},
        "status": "pending",
        "attempt_ids": [],
    }


def parse_guardrail_score(value: str) -> tuple[str, float]:
    key, separator, raw_score = value.partition("=")
    if not separator or not key or not raw_score:
        raise argparse.ArgumentTypeError("guardrail score must be key=value")
    try:
        score = float(raw_score)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("guardrail score must be numeric") from exc
    if score < 0 or score > 1:
        raise argparse.ArgumentTypeError("guardrail score must be between 0 and 1")
    return key, score


def score_map(items: list[tuple[str, float]] | None) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, score in items or []:
        result[key] = score
    return result


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def provenance_payload(
    *,
    created_by: str,
    source_repo: str,
    source_commit: str,
    skill_version: str,
    host: str,
    model: str,
    generated_at: str,
    input_refs: list[str],
    verification_refs: list[str],
) -> dict[str, Any]:
    return {
        "created_by": created_by,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "skill_version": skill_version,
        "host": host,
        "model": model,
        "generated_at": generated_at,
        "input_refs": input_refs,
        "verification_refs": verification_refs,
    }


def provenance_failures(data: dict[str, Any], *, field_name: str = "provenance") -> list[str]:
    failures: list[str] = []
    provenance = data.get(field_name)
    if not isinstance(provenance, dict):
        return [f"{field_name} must be an object"]
    for field in PROVENANCE_REQUIRED_FIELDS:
        if field not in provenance:
            failures.append(f"{field_name} missing {field}")
    for field in ("created_by", "source_repo", "source_commit", "skill_version", "host", "model", "generated_at"):
        if field in provenance and (not isinstance(provenance[field], str) or not provenance[field]):
            failures.append(f"{field_name}.{field} must be a non-empty string")
    for field in ("input_refs", "verification_refs"):
        if field in provenance and not isinstance(provenance[field], list):
            failures.append(f"{field_name}.{field} must be a list")
        elif field in provenance:
            invalid = [item for item in provenance[field] if not isinstance(item, str) or not item]
            if invalid:
                failures.append(f"{field_name}.{field} must contain only non-empty strings")
    return failures


def open_todos(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [todo for todo in data.get("todos") or [] if todo.get("status") in OPEN_TODO_STATUSES]


def current_todo(data: dict[str, Any]) -> dict[str, Any] | None:
    open_items = open_todos(data)
    for todo in open_items:
        if todo.get("status") == "in_progress":
            return todo
    return open_items[0] if open_items else None


def run_summary(data: dict[str, Any]) -> dict[str, Any]:
    active_todo = current_todo(data) or {}
    attempts = data.get("attempt_ledger") or []
    last_attempt = attempts[-1] if attempts else {}
    verification_refs = data.get("verification_evidence") or []
    blockers = data.get("blockers") or []
    uigwe_reentry_requests = data.get("uigwe_reentry_requests") or []
    open_count = len(open_todos(data))
    status = data.get("status")
    current_todo_id = active_todo.get("todo_id")

    if status == "completed":
        next_action = "no_action_completed"
    elif blockers:
        next_action = "resolve_blocker_or_reenter_uigwe"
    elif status == "blocked":
        next_action = "resolve_blocker_or_reenter_uigwe"
    elif status == "active" and current_todo_id:
        next_action = f"continue_todo:{current_todo_id}"
    elif status == "active" and verification_refs:
        next_action = "complete_or_block_run"
    elif status == "active":
        next_action = "add_actionable_todo_or_record_blocker"
    else:
        next_action = "inspect_run_status"

    return {
        "format": "sejong.seungjeongwon-run-summary/v0.1-draft",
        "run_id": data.get("run_id"),
        "status": status,
        "goal": data.get("goal"),
        "open_todo_count": open_count,
        "current_todo_id": current_todo_id,
        "current_todo_description": active_todo.get("description"),
        "attempt_count": len(attempts),
        "last_attempt_id": last_attempt.get("attempt_id"),
        "last_attempt_result": last_attempt.get("result"),
        "last_attempt_next_decision": last_attempt.get("next_decision"),
        "verification_evidence_count": len(verification_refs),
        "last_verification_ref": verification_refs[-1] if verification_refs else None,
        "blocker_count": len(blockers),
        "uigwe_reentry_request_count": len(uigwe_reentry_requests),
        "next_action": next_action,
    }


def format_run_summary(data: dict[str, Any]) -> str:
    summary = run_summary(data)
    current_todo_id = summary.get("current_todo_id") or "none"
    last_attempt_id = summary.get("last_attempt_id") or "none"
    return (
        f"{summary.get('run_id')} "
        f"open_todos={summary.get('open_todo_count')} "
        f"status={summary.get('status')} "
        f"current_todo={current_todo_id} "
        f"blockers={summary.get('blocker_count')} "
        f"last_attempt={last_attempt_id} "
        f"next_action={summary.get('next_action')}"
    )


def todo_by_id(data: dict[str, Any], todo_id: str) -> dict[str, Any] | None:
    for todo in data.get("todos") or []:
        if todo.get("todo_id") == todo_id:
            return todo
    return None


def run_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = [
        "format",
        "run_id",
        "repo_root",
        "provenance",
        "goal",
        "status",
        "success_criteria",
        "verification_methods",
        "guardrail_thresholds",
        "todos",
        "attempt_ledger",
        "verification_evidence",
        "guardrail_scores",
        "blockers",
        "uigwe_reentry_requests",
        "created_at",
        "updated_at",
    ]
    for field in required:
        if field not in data:
            failures.append(f"missing {field}")
    if data.get("format") != RUN_FORMAT:
        failures.append(f"unexpected format: {data.get('format')}")
    if data.get("status") not in STATUSES:
        failures.append(f"unsupported run status: {data.get('status')}")
    failures.extend(provenance_failures(data))
    for field in ("success_criteria", "verification_methods", "todos", "attempt_ledger", "verification_evidence", "blockers", "uigwe_reentry_requests"):
        if field in data and not isinstance(data.get(field), list):
            failures.append(f"{field} must be a list")
    guardrail_thresholds = data.get("guardrail_thresholds")
    if not isinstance(guardrail_thresholds, dict):
        failures.append("guardrail_thresholds must be an object")
        guardrail_thresholds = {}
    for field in ("leaf_guardrail_minimum", "leaf_guardrail_aggregate", "run_guardrail_aggregate", "selected_leaf_coverage", "success_criteria_coverage"):
        value = guardrail_thresholds.get(field)
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            failures.append(f"guardrail_thresholds.{field} must be a number between 0 and 1")
    leaf_minimum = float(guardrail_thresholds.get("leaf_guardrail_minimum", DEFAULT_GUARDRAIL_THRESHOLD))
    leaf_aggregate = float(guardrail_thresholds.get("leaf_guardrail_aggregate", DEFAULT_GUARDRAIL_THRESHOLD))
    run_aggregate = float(guardrail_thresholds.get("run_guardrail_aggregate", DEFAULT_GUARDRAIL_THRESHOLD))
    selected_leaf_coverage = float(guardrail_thresholds.get("selected_leaf_coverage", DEFAULT_COVERAGE_THRESHOLD))
    success_criteria_coverage = float(guardrail_thresholds.get("success_criteria_coverage", DEFAULT_COVERAGE_THRESHOLD))

    attempt_ids = {attempt.get("attempt_id") for attempt in data.get("attempt_ledger") or []}
    todo_ids: set[str] = set()
    for todo in data.get("todos") or []:
        todo_id = todo.get("todo_id")
        if not todo_id:
            failures.append("todo missing todo_id")
            continue
        if todo_id in todo_ids:
            failures.append(f"duplicate todo_id: {todo_id}")
        todo_ids.add(todo_id)
        for field in ("description", "done_criteria", "verification_method", "guardrail_scores", "status", "attempt_ids"):
            if field not in todo:
                failures.append(f"todo {todo_id} missing {field}")
        if todo.get("status") not in TODO_STATUSES:
            failures.append(f"todo {todo_id} has unsupported status: {todo.get('status')}")
        todo_attempt_ids = todo.get("attempt_ids") or []
        if not isinstance(todo_attempt_ids, list):
            failures.append(f"todo {todo_id} attempt_ids must be a list")
            todo_attempt_ids = []
        missing_attempts = sorted(set(todo_attempt_ids) - attempt_ids)
        if missing_attempts:
            failures.append(f"todo {todo_id} references missing attempts: {', '.join(missing_attempts)}")
        if todo.get("status") == "completed" and not todo_attempt_ids:
            failures.append(f"completed todo requires at least one attempt: {todo_id}")
        todo_scores = todo.get("guardrail_scores")
        if todo.get("status") == "completed":
            if not isinstance(todo_scores, dict) or not todo_scores:
                failures.append(f"completed todo requires guardrail scores: {todo_id}")
            else:
                for score_name, score in todo_scores.items():
                    if not isinstance(score, (int, float)) or score < 0 or score > 1:
                        failures.append(f"todo {todo_id} guardrail score {score_name} must be between 0 and 1")
                    elif score_name == "overall" and score < leaf_aggregate:
                        failures.append(f"completed todo overall guardrail score below threshold: {todo_id} {score} < {leaf_aggregate}")
                    elif score_name != "overall" and score < leaf_minimum:
                        failures.append(f"completed todo guardrail score below threshold: {todo_id} {score_name}={score} < {leaf_minimum}")
                if "overall" not in todo_scores:
                    failures.append(f"completed todo requires overall guardrail score: {todo_id}")

    for attempt in data.get("attempt_ledger") or []:
        attempt_id = attempt.get("attempt_id")
        for field in (
            "attempt_id",
            "todo_id",
            "hypothesis",
            "action",
            "verification",
            "result",
            "finding",
            "next_decision",
            "created_at",
        ):
            if not attempt.get(field):
                failures.append(f"attempt {attempt_id or '<missing>'} missing {field}")
        if attempt.get("todo_id") and attempt.get("todo_id") not in todo_ids:
            failures.append(f"attempt references unknown todo: {attempt.get('attempt_id')}")

    if data.get("status") == "completed":
        if open_todos(data):
            failures.append("completed run cannot have open todos")
        if not data.get("verification_evidence"):
            failures.append("completed run requires verification evidence")
        run_scores = data.get("guardrail_scores")
        if not isinstance(run_scores, dict) or not run_scores:
            failures.append("completed run requires guardrail scores")
        else:
            for score_name, score in run_scores.items():
                if not isinstance(score, (int, float)) or score < 0 or score > 1:
                    failures.append(f"run guardrail score {score_name} must be between 0 and 1")
                elif score_name == "selected_leaf_coverage" and score < selected_leaf_coverage:
                    failures.append(f"completed run selected leaf coverage below threshold: {score} < {selected_leaf_coverage}")
                elif score_name == "success_criteria_coverage" and score < success_criteria_coverage:
                    failures.append(f"completed run success criteria coverage below threshold: {score} < {success_criteria_coverage}")
                elif score < run_aggregate:
                    failures.append(f"completed run guardrail score below threshold: {score_name}={score} < {run_aggregate}")
            if "overall" not in run_scores:
                failures.append("completed run requires overall guardrail score")
            if "selected_leaf_coverage" not in run_scores:
                failures.append("completed run requires selected_leaf_coverage guardrail score")
            if "success_criteria_coverage" not in run_scores:
                failures.append("completed run requires success_criteria_coverage guardrail score")
    if data.get("status") == "active" and data.get("verification_evidence") and not open_todos(data):
        failures.append("active run with verification evidence and no open todos should be completed or blocked")
    return failures


def emit_failures(failures: list[str]) -> int:
    for failure in failures:
        print(f"failure: {failure}", file=sys.stderr)
    return 1 if failures else 0


def resolve_optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    return str(resolve_path(value))


def git_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            timeout=3,
        )
    except Exception:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def checkpoint_payload(data: dict[str, Any], run_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    timestamp = now_utc()
    run_provenance = data.get("provenance") or {}
    return {
        "format": CHECKPOINT_FORMAT,
        "checkpoint_id": args.checkpoint_id or f"checkpoint-{data['run_id']}-{timestamp}",
        "run_id": data["run_id"],
        "repo_root": data["repo_root"],
        "source_run_path": str(resolve_path(run_path)),
        "source_run_updated_at": data["updated_at"],
        "provenance": provenance_payload(
            created_by="seungjeongwon",
            source_repo=run_provenance.get("source_repo") or data["repo_root"],
            source_commit=run_provenance.get("source_commit") or "unknown",
            skill_version=run_provenance.get("skill_version") or "unknown",
            host=run_provenance.get("host") or "codex",
            model=run_provenance.get("model") or "unknown",
            generated_at=timestamp,
            input_refs=unique_strings([str(resolve_path(run_path)), *(run_provenance.get("input_refs") or [])]),
            verification_refs=unique_strings(
                [*(data.get("verification_evidence") or []), *(run_provenance.get("verification_refs") or [])]
            ),
        ),
        "context_id": args.context_id,
        "objective_id": args.objective_id,
        "approved_goal": data["goal"],
        "status": data["status"],
        "success_criteria": data["success_criteria"],
        "verification_methods": data["verification_methods"],
        "guardrail_thresholds": data["guardrail_thresholds"],
        "active_todos": open_todos(data),
        "todo_statuses": [
            {
                "todo_id": todo.get("todo_id"),
                "status": todo.get("status"),
                "attempt_ids": todo.get("attempt_ids") or [],
            }
            for todo in data.get("todos") or []
        ],
        "attempt_ledger": data["attempt_ledger"],
        "verification_evidence": data["verification_evidence"],
        "guardrail_scores": data["guardrail_scores"],
        "blockers": data["blockers"],
        "uigwe_reentry_requests": data["uigwe_reentry_requests"],
        "created_at": timestamp,
    }


def checkpoint_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = [
        "format",
        "checkpoint_id",
        "run_id",
        "repo_root",
        "source_run_path",
        "source_run_updated_at",
        "provenance",
        "context_id",
        "objective_id",
        "approved_goal",
        "status",
        "success_criteria",
        "verification_methods",
        "guardrail_thresholds",
        "active_todos",
        "todo_statuses",
        "attempt_ledger",
        "verification_evidence",
        "guardrail_scores",
        "blockers",
        "uigwe_reentry_requests",
        "created_at",
    ]
    for field in required:
        if field not in data:
            failures.append(f"checkpoint missing {field}")
    if data.get("format") != CHECKPOINT_FORMAT:
        failures.append(f"unexpected checkpoint format: {data.get('format')}")
    failures.extend(provenance_failures(data))
    for field in (
        "success_criteria",
        "verification_methods",
        "active_todos",
        "todo_statuses",
        "attempt_ledger",
        "verification_evidence",
        "blockers",
        "uigwe_reentry_requests",
    ):
        if field in data and not isinstance(data.get(field), list):
            failures.append(f"checkpoint {field} must be a list")
    if "guardrail_thresholds" in data and not isinstance(data.get("guardrail_thresholds"), dict):
        failures.append("checkpoint guardrail_thresholds must be an object")
    if "guardrail_scores" in data and not isinstance(data.get("guardrail_scores"), dict):
        failures.append("checkpoint guardrail_scores must be an object")
    for field in ("checkpoint_id", "run_id", "repo_root", "source_run_path", "source_run_updated_at", "approved_goal", "status", "created_at"):
        if field in data and not data.get(field):
            failures.append(f"checkpoint {field} must be non-empty")
    return failures


def resume_payload(checkpoint: dict[str, Any], *, format_name: str) -> dict[str, Any]:
    return {
        "format": format_name,
        "checkpoint_id": checkpoint["checkpoint_id"],
        "run_id": checkpoint["run_id"],
        "repo_root": checkpoint["repo_root"],
        "provenance": checkpoint["provenance"],
        "context_id": checkpoint.get("context_id"),
        "objective_id": checkpoint.get("objective_id"),
        "approved_goal": checkpoint["approved_goal"],
        "status": checkpoint["status"],
        "success_criteria": checkpoint["success_criteria"],
        "verification_methods": checkpoint["verification_methods"],
        "guardrail_thresholds": checkpoint["guardrail_thresholds"],
        "active_todos": checkpoint["active_todos"],
        "attempt_ledger": checkpoint["attempt_ledger"],
        "verification_evidence": checkpoint["verification_evidence"],
        "blockers": checkpoint["blockers"],
        "uigwe_reentry_requests": checkpoint["uigwe_reentry_requests"],
        "source_run_updated_at": checkpoint["source_run_updated_at"],
        "stale_context_rejected": False,
        "replayed_at": now_utc(),
    }


def write_or_print_json(output_path: str | None, data: dict[str, Any]) -> None:
    if output_path:
        write_json(Path(output_path), data)
        print(f"written: {output_path}")
        return
    print(json.dumps(data, indent=2, sort_keys=True))


def replay_stale_failures(
    checkpoint: dict[str, Any],
    run_data: dict[str, Any],
    *,
    expected_repo_root: str | None,
    expected_context_id: str | None,
    expected_objective_id: str | None,
) -> list[str]:
    failures = checkpoint_failures(checkpoint)
    failures.extend(run_failures(run_data))
    if failures:
        return failures
    if checkpoint["run_id"] != run_data["run_id"]:
        failures.append(f"stale checkpoint run_id mismatch: {checkpoint['run_id']} != {run_data['run_id']}")
    if checkpoint["repo_root"] != run_data["repo_root"]:
        failures.append(f"stale checkpoint repo_root mismatch: {checkpoint['repo_root']} != {run_data['repo_root']}")
    if expected_repo_root and checkpoint["repo_root"] != expected_repo_root:
        failures.append(f"stale checkpoint expected repo_root mismatch: {checkpoint['repo_root']} != {expected_repo_root}")
    if expected_context_id and checkpoint.get("context_id") != expected_context_id:
        failures.append(f"stale checkpoint context_id mismatch: {checkpoint.get('context_id')} != {expected_context_id}")
    if expected_objective_id and checkpoint.get("objective_id") != expected_objective_id:
        failures.append(f"stale checkpoint objective_id mismatch: {checkpoint.get('objective_id')} != {expected_objective_id}")
    if checkpoint["source_run_updated_at"] != run_data["updated_at"]:
        failures.append(
            f"stale checkpoint source_run_updated_at mismatch: {checkpoint['source_run_updated_at']} != {run_data['updated_at']}"
        )
    if checkpoint["approved_goal"] != run_data["goal"]:
        failures.append("stale checkpoint approved_goal mismatch")
    if checkpoint["active_todos"] != open_todos(run_data):
        failures.append("stale checkpoint active_todos mismatch")
    for field in ("attempt_ledger", "verification_evidence", "guardrail_scores", "blockers", "uigwe_reentry_requests"):
        if checkpoint.get(field) != run_data.get(field):
            failures.append(f"stale checkpoint {field} mismatch")
    return failures


def start(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"run already exists: {path}", file=sys.stderr)
        return 1
    timestamp = now_utc()
    repo_root = str(resolve_path(args.repo_root))
    source_commit = args.source_commit or os.environ.get("SEJONG_SOURCE_COMMIT") or git_head(Path(repo_root))
    data = {
        "format": RUN_FORMAT,
        "run_id": args.run_id,
        "repo_root": repo_root,
        "provenance": provenance_payload(
            created_by="seungjeongwon",
            source_repo=repo_root,
            source_commit=source_commit,
            skill_version=args.skill_version or os.environ.get("SEJONG_SKILL_VERSION") or "0.1.0",
            host=args.host,
            model=args.model or os.environ.get("SEJONG_MODEL") or "unknown",
            generated_at=timestamp,
            input_refs=args.input_ref or [],
            verification_refs=[],
        ),
        "goal": args.goal,
        "status": "active",
        "success_criteria": args.success_criterion,
        "verification_methods": args.verification_method,
        "guardrail_thresholds": {
            "leaf_guardrail_minimum": args.leaf_guardrail_minimum,
            "leaf_guardrail_aggregate": args.leaf_guardrail_aggregate,
            "run_guardrail_aggregate": args.run_guardrail_aggregate,
            "selected_leaf_coverage": args.selected_leaf_coverage,
            "success_criteria_coverage": args.success_criteria_coverage,
        },
        "todos": args.todo or [],
        "attempt_ledger": [],
        "verification_evidence": [],
        "guardrail_scores": {},
        "blockers": [],
        "uigwe_reentry_requests": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"run started: {path}")
    return 0


def check(args: argparse.Namespace) -> int:
    data = load_json(Path(args.path))
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    print(f"seungjeongwon run ok: {Path(args.path)}")
    return 0


def summary(args: argparse.Namespace) -> int:
    data = load_json(Path(args.path))
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    if args.json:
        print(json.dumps(run_summary(data), indent=2, sort_keys=True))
        return 0
    print(format_run_summary(data))
    return 0


def record_attempt(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    todo = todo_by_id(data, args.todo_id)
    if todo is None:
        print(f"unknown todo: {args.todo_id}", file=sys.stderr)
        return 1
    attempt_id = args.attempt_id or f"A{len(data.get('attempt_ledger') or []) + 1}"
    attempt = {
        "attempt_id": attempt_id,
        "todo_id": args.todo_id,
        "hypothesis": args.hypothesis,
        "action": args.action,
        "verification": args.verification,
        "result": args.result,
        "finding": args.finding,
        "next_decision": args.next_decision,
        "evidence_refs": args.evidence_ref or [],
        "created_at": now_utc(),
    }
    data.setdefault("attempt_ledger", []).append(attempt)
    todo.setdefault("attempt_ids", []).append(attempt_id)
    if todo.get("status") == "pending":
        todo["status"] = "in_progress"
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"attempt recorded: {attempt_id}")
    return 0


def complete_todo(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    todo = todo_by_id(data, args.todo_id)
    if todo is None:
        print(f"unknown todo: {args.todo_id}", file=sys.stderr)
        return 1
    if not todo.get("attempt_ids"):
        print(f"todo requires at least one attempt before completion: {args.todo_id}", file=sys.stderr)
        return 1
    todo["guardrail_scores"] = score_map(args.guardrail_score)
    todo["status"] = "completed"
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"todo completed: {args.todo_id}")
    return 0


def complete(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    if open_todos(data):
        print("open todos remain; cannot complete run", file=sys.stderr)
        return 1
    data.setdefault("verification_evidence", []).append(args.verification_evidence)
    if isinstance(data.get("provenance"), dict):
        data["provenance"]["verification_refs"] = unique_strings(
            [*(data["provenance"].get("verification_refs") or []), args.verification_evidence]
        )
    data["guardrail_scores"] = score_map(args.guardrail_score)
    data["status"] = "completed"
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"run completed: {path}")
    return 0


def checkpoint(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load_json(path)
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    payload = checkpoint_payload(data, path, args)
    failures = checkpoint_failures(payload)
    if failures:
        return emit_failures(failures)
    write_or_print_json(args.output, payload)
    return 0


def resume(args: argparse.Namespace) -> int:
    checkpoint_data = load_json(Path(args.checkpoint))
    failures = checkpoint_failures(checkpoint_data)
    expected_repo_root = resolve_optional_path(args.expect_repo_root)
    if expected_repo_root and checkpoint_data.get("repo_root") != expected_repo_root:
        failures.append(f"stale checkpoint expected repo_root mismatch: {checkpoint_data.get('repo_root')} != {expected_repo_root}")
    if args.expect_context_id and checkpoint_data.get("context_id") != args.expect_context_id:
        failures.append(f"stale checkpoint context_id mismatch: {checkpoint_data.get('context_id')} != {args.expect_context_id}")
    if args.expect_objective_id and checkpoint_data.get("objective_id") != args.expect_objective_id:
        failures.append(f"stale checkpoint objective_id mismatch: {checkpoint_data.get('objective_id')} != {args.expect_objective_id}")
    if failures:
        return emit_failures(failures)
    write_or_print_json(args.output, resume_payload(checkpoint_data, format_name=RESUME_FORMAT))
    return 0


def stale_check(args: argparse.Namespace) -> int:
    checkpoint_data = load_json(Path(args.checkpoint))
    run_data = load_json(Path(args.path))
    failures = replay_stale_failures(
        checkpoint_data,
        run_data,
        expected_repo_root=resolve_optional_path(args.expect_repo_root),
        expected_context_id=args.expect_context_id,
        expected_objective_id=args.expect_objective_id,
    )
    if failures:
        return emit_failures(failures)
    print(f"checkpoint fresh: {Path(args.checkpoint)}")
    return 0


def replay(args: argparse.Namespace) -> int:
    checkpoint_data = load_json(Path(args.checkpoint))
    run_data = load_json(Path(args.path))
    failures = replay_stale_failures(
        checkpoint_data,
        run_data,
        expected_repo_root=resolve_optional_path(args.expect_repo_root),
        expected_context_id=args.expect_context_id,
        expected_objective_id=args.expect_objective_id,
    )
    if failures:
        return emit_failures(failures)
    write_or_print_json(args.output, resume_payload(checkpoint_data, format_name=REPLAY_FORMAT))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a Seungjeongwon active execution run artifact.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a Seungjeongwon run artifact.")
    start_parser.add_argument("--path", required=True)
    start_parser.add_argument("--run-id", required=True)
    start_parser.add_argument("--repo-root", default=".")
    start_parser.add_argument("--goal", required=True)
    start_parser.add_argument("--source-commit")
    start_parser.add_argument("--skill-version")
    start_parser.add_argument("--host", default=os.environ.get("SEJONG_HOST", "codex"))
    start_parser.add_argument("--model")
    start_parser.add_argument("--input-ref", action="append")
    start_parser.add_argument("--success-criterion", action="append", required=True)
    start_parser.add_argument("--verification-method", action="append", required=True)
    start_parser.add_argument("--leaf-guardrail-minimum", type=float, default=DEFAULT_GUARDRAIL_THRESHOLD)
    start_parser.add_argument("--leaf-guardrail-aggregate", type=float, default=DEFAULT_GUARDRAIL_THRESHOLD)
    start_parser.add_argument("--run-guardrail-aggregate", type=float, default=DEFAULT_GUARDRAIL_THRESHOLD)
    start_parser.add_argument("--selected-leaf-coverage", type=float, default=DEFAULT_COVERAGE_THRESHOLD)
    start_parser.add_argument("--success-criteria-coverage", type=float, default=DEFAULT_COVERAGE_THRESHOLD)
    start_parser.add_argument("--todo", action="append", type=parse_todo)
    start_parser.add_argument("--force", action="store_true")
    start_parser.set_defaults(func=start)

    check_parser = subparsers.add_parser("check", help="Validate a Seungjeongwon run artifact.")
    check_parser.add_argument("--path", required=True)
    check_parser.set_defaults(func=check)

    summary_parser = subparsers.add_parser("summary", help="Print the current run HUD summary.")
    summary_parser.add_argument("--path", required=True)
    summary_parser.add_argument("--json", action="store_true")
    summary_parser.set_defaults(func=summary)

    attempt_parser = subparsers.add_parser("record-attempt", help="Append an execution attempt.")
    attempt_parser.add_argument("--path", required=True)
    attempt_parser.add_argument("--attempt-id")
    attempt_parser.add_argument("--todo-id", required=True)
    attempt_parser.add_argument("--hypothesis", required=True)
    attempt_parser.add_argument("--action", required=True)
    attempt_parser.add_argument("--verification", required=True)
    attempt_parser.add_argument("--result", required=True)
    attempt_parser.add_argument("--finding", required=True)
    attempt_parser.add_argument("--next-decision", required=True)
    attempt_parser.add_argument("--evidence-ref", action="append")
    attempt_parser.set_defaults(func=record_attempt)

    todo_parser = subparsers.add_parser("complete-todo", help="Mark a todo completed after at least one attempt.")
    todo_parser.add_argument("--path", required=True)
    todo_parser.add_argument("--todo-id", required=True)
    todo_parser.add_argument("--guardrail-score", action="append", type=parse_guardrail_score, required=True)
    todo_parser.set_defaults(func=complete_todo)

    complete_parser = subparsers.add_parser("complete", help="Mark the run completed after all todos close.")
    complete_parser.add_argument("--path", required=True)
    complete_parser.add_argument("--verification-evidence", required=True)
    complete_parser.add_argument("--guardrail-score", action="append", type=parse_guardrail_score, required=True)
    complete_parser.set_defaults(func=complete)

    checkpoint_parser = subparsers.add_parser("checkpoint", help="Write a compact replay checkpoint from a run artifact.")
    checkpoint_parser.add_argument("--path", required=True)
    checkpoint_parser.add_argument("--output")
    checkpoint_parser.add_argument("--checkpoint-id")
    checkpoint_parser.add_argument("--context-id")
    checkpoint_parser.add_argument("--objective-id")
    checkpoint_parser.set_defaults(func=checkpoint)

    resume_parser = subparsers.add_parser("resume", help="Materialize resume context from a checkpoint.")
    resume_parser.add_argument("--checkpoint", required=True)
    resume_parser.add_argument("--output")
    resume_parser.add_argument("--expect-repo-root")
    resume_parser.add_argument("--expect-context-id")
    resume_parser.add_argument("--expect-objective-id")
    resume_parser.set_defaults(func=resume)

    stale_parser = subparsers.add_parser("stale-check", help="Reject a checkpoint that no longer matches the active run.")
    stale_parser.add_argument("--checkpoint", required=True)
    stale_parser.add_argument("--path", required=True)
    stale_parser.add_argument("--expect-repo-root")
    stale_parser.add_argument("--expect-context-id")
    stale_parser.add_argument("--expect-objective-id")
    stale_parser.set_defaults(func=stale_check)

    replay_parser = subparsers.add_parser("replay", help="Replay a fresh checkpoint into compact resume context.")
    replay_parser.add_argument("--checkpoint", required=True)
    replay_parser.add_argument("--path", required=True)
    replay_parser.add_argument("--output")
    replay_parser.add_argument("--expect-repo-root")
    replay_parser.add_argument("--expect-context-id")
    replay_parser.add_argument("--expect-objective-id")
    replay_parser.set_defaults(func=replay)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
