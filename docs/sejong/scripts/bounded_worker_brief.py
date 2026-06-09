#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


BRIEF_FORMAT = "sejong.bounded-worker-brief/v0.2-draft"
COMPATIBLE_FORMATS = {
    BRIEF_FORMAT,
    "sejong.team-worker/v0.1-draft",
}

REQUIRED_FIELDS = (
    "objective",
    "role",
    "source_of_truth_refs",
    "allowed_outputs",
    "forbidden_claims",
    "write_scope",
    "stop_condition",
    "evidence_refs",
)

LIST_FIELDS = (
    "source_of_truth_refs",
    "allowed_outputs",
    "forbidden_claims",
    "write_scope",
    "evidence_refs",
)

FORBIDDEN_AUTHORITY_TERMS = (
    "approve the uigwe gate",
    "approved the uigwe gate",
    "uigwe gate approved",
    "gate approved",
    "final decision",
    "final synthesis",
    "final verification",
    "majority vote",
    "by majority",
    "consensus approves",
    "consensus approval",
)

REQUIRED_FORBIDDEN_CLAIM_FRAGMENTS = (
    "uigwe gate",
    "final synthesis",
    "final verification",
    "majority",
    "consensus",
)


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list_failures(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list"]
    failures: list[str] = []
    for index, item in enumerate(value):
        if not non_empty_string(item):
            failures.append(f"{field}[{index}] must be a non-empty string")
    return failures


def text_claims_forbidden_authority(value: str) -> str | None:
    lowered = value.lower()
    for term in FORBIDDEN_AUTHORITY_TERMS:
        if term in lowered:
            return term
    return None


def validate_bounded_worker_brief(
    brief: dict[str, Any],
    *,
    expected_source_of_truth_refs: list[str] | None = None,
    label: str = "worker brief",
) -> list[str]:
    brief = dict(brief)
    if "forbidden_claims" not in brief and "forbidden_worker_claims" in brief:
        brief["forbidden_claims"] = brief["forbidden_worker_claims"]

    failures: list[str] = []
    if brief.get("format") is not None and brief.get("format") not in COMPATIBLE_FORMATS:
        failures.append(f"{label} has unexpected format: {brief.get('format')}")

    for field in REQUIRED_FIELDS:
        if field not in brief:
            failures.append(f"{label} missing {field}")

    for field in ("objective", "role", "stop_condition"):
        if field in brief and not non_empty_string(brief.get(field)):
            failures.append(f"{label} {field} must be a non-empty string")

    for field in LIST_FIELDS:
        if field in brief:
            failures.extend(f"{label} {failure}" for failure in string_list_failures(brief.get(field), field))

    expected_refs = set(expected_source_of_truth_refs or [])
    brief_refs = set(brief.get("source_of_truth_refs") or [])
    missing_refs = sorted(expected_refs - brief_refs)
    if missing_refs:
        failures.append(f"{label} source_of_truth_refs missing expected refs: {missing_refs}")

    forbidden_claims = [str(item).lower() for item in (brief.get("forbidden_claims") or [])]
    for fragment in REQUIRED_FORBIDDEN_CLAIM_FRAGMENTS:
        if not any(fragment in claim for claim in forbidden_claims):
            failures.append(f"{label} forbidden_claims missing {fragment}")

    for field in ("objective", "role", "stop_condition"):
        value = brief.get(field)
        if isinstance(value, str):
            forbidden = text_claims_forbidden_authority(value)
            if forbidden:
                failures.append(f"{label} {field} claims forbidden authority: {forbidden}")

    for field in ("allowed_outputs", "write_scope", "evidence_refs"):
        for item in brief.get(field) or []:
            if not isinstance(item, str):
                continue
            forbidden = text_claims_forbidden_authority(item)
            if forbidden:
                failures.append(f"{label} {field} claims forbidden authority: {forbidden}")

    for scope in brief.get("write_scope") or []:
        if isinstance(scope, str) and scope.strip().startswith(".omx"):
            failures.append(f"{label} write_scope must not depend on .omx state: {scope}")

    return failures


def brief_from_team_worker(team: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    source_refs = worker.get("source_of_truth_refs") or team.get("source_of_truth_refs") or []
    evidence_refs = worker.get("evidence_refs") or source_refs
    return {
        "format": BRIEF_FORMAT,
        "objective": worker.get("objective") or worker.get("scope"),
        "role": worker.get("role"),
        "source_of_truth_refs": source_refs,
        "allowed_outputs": worker.get("allowed_outputs") or [],
        "forbidden_claims": worker.get("forbidden_worker_claims") or team.get("forbidden_worker_claims") or [],
        "write_scope": worker.get("write_scope") or [],
        "stop_condition": worker.get("stop_condition"),
        "evidence_refs": evidence_refs,
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("usage: bounded_worker_brief.py <brief.json>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    failures = validate_bounded_worker_brief(load_json(path), label=str(path))
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    print(f"bounded worker brief ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
