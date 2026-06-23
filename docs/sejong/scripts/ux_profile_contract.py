#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


FORMAT = "sejong.ux-profile-output/v0.1-draft"
PROFILES = {"compact/default", "expanded/detail", "bounded-specialist-evidence"}
SURFACES = {"sejong", "jangyeongsil", "jiphyeonjeon", "uigwe", "seungjeongwon", "sillok"}
CLAIM_TYPES = {"presentation", "evidence", "diagnostic", "status", "handoff_input"}
REQUIRED_FORBIDDEN_CLAIMS = {"no_gate_approval", "no_execution_approval", "no_completion_claim"}
FORBIDDEN_AUTHORITY_TERMS = (
    "approve uigwe gate",
    "approved uigwe gate",
    "waive approval",
    "waived approval",
    "final decision",
    "final synthesis",
    "final verification",
    "completion verified",
    "execution approved",
    "gate approved",
    "consensus approval",
)


def text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(text_values(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(text_values(item))
        return result
    return []


def ux_profile_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if data.get("format") != FORMAT:
        failures.append(f"unexpected format: {data.get('format')}")
    if data.get("profile") not in PROFILES:
        failures.append(f"unsupported profile: {data.get('profile')}")
    if data.get("owner_surface") not in SURFACES:
        failures.append(f"unsupported owner_surface: {data.get('owner_surface')}")
    if data.get("next_surface") not in SURFACES:
        failures.append(f"unsupported next_surface: {data.get('next_surface')}")
    if data.get("claim_type") not in CLAIM_TYPES:
        failures.append(f"unsupported claim_type: {data.get('claim_type')}")
    for field in ("known", "inferred", "unknown", "forbidden_claims"):
        if field not in data:
            failures.append(f"missing {field}")
        elif not isinstance(data.get(field), list):
            failures.append(f"{field} must be a list")
    forbidden_claims = set(data.get("forbidden_claims") or [])
    missing_claims = sorted(REQUIRED_FORBIDDEN_CLAIMS - forbidden_claims)
    if missing_claims:
        failures.append("missing required forbidden_claims: " + ", ".join(missing_claims))
    if data.get("authority_claims"):
        failures.append("profile output cannot carry authority_claims")
    if data.get("approvals"):
        failures.append("profile output cannot carry approvals")
    if data.get("completion_claim"):
        failures.append("profile output cannot claim completion")
    combined = "\n".join(text_values(data)).casefold()
    for term in FORBIDDEN_AUTHORITY_TERMS:
        if term in combined:
            failures.append(f"forbidden authority term: {term}")
    return failures


def check_path(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    failures = ux_profile_failures(data)
    for failure in failures:
        print(f"failure: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"ux profile output ok: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate King Sejong UX profile output boundaries.")
    parser.add_argument("path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return check_path(Path(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
