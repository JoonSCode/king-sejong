#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sejong_paths import resolve_path


RUN_FORMAT = "sejong.seungjeongwon-run/v0.1-draft"
STATUSES = {"active", "completed", "blocked", "invalidated", "failed"}
OPEN_TODO_STATUSES = {"pending", "in_progress"}
CLOSED_TODO_STATUSES = {"completed", "blocked", "invalidated", "replaced"}
TODO_STATUSES = OPEN_TODO_STATUSES | CLOSED_TODO_STATUSES
DEFAULT_GUARDRAIL_THRESHOLD = 0.98
DEFAULT_COVERAGE_THRESHOLD = 1.0


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


def open_todos(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [todo for todo in data.get("todos") or [] if todo.get("status") in OPEN_TODO_STATUSES]


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


def start(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"run already exists: {path}", file=sys.stderr)
        return 1
    timestamp = now_utc()
    data = {
        "format": RUN_FORMAT,
        "run_id": args.run_id,
        "repo_root": str(resolve_path(args.repo_root)),
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
    data["guardrail_scores"] = score_map(args.guardrail_score)
    data["status"] = "completed"
    data["updated_at"] = now_utc()
    failures = run_failures(data)
    if failures:
        return emit_failures(failures)
    write_json(path, data)
    print(f"run completed: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a Seungjeongwon active execution run artifact.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Create a Seungjeongwon run artifact.")
    start_parser.add_argument("--path", required=True)
    start_parser.add_argument("--run-id", required=True)
    start_parser.add_argument("--repo-root", default=".")
    start_parser.add_argument("--goal", required=True)
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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
