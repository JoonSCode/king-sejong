#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TRANSIENT_TERMS = (
    "/tmp/",
    "/var/folders/",
    "current session",
    "this session",
    "scratch",
    "temporary",
    "today only",
)

DEFAULT_SECTION = """<!-- BEGIN King Sejong Repo Context Candidate -->
# Agent Context

This repository can use King Sejong for broad or goal-bearing agent work.
Use Sejong for research, option comparison, planning, execution, verification, and evidence records when the request is ambiguous or outcome-bearing.

Keep durable repository guidance in AGENTS.md or the appropriate project docs. Keep temporary Sejong runtime artifacts outside the repository under ${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong} unless the user explicitly promotes a tracked artifact.
<!-- END King Sejong Repo Context Candidate -->"""


def reject_reason(lesson: str) -> str | None:
    lowered = lesson.casefold()
    for term in TRANSIENT_TERMS:
        if term in lowered:
            return f"contains transient term: {term}"
    if len(lesson.strip()) < 12:
        return "too short to be durable guidance"
    return None


def classify_lessons(lessons: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    accepted: list[str] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()
    for lesson in lessons:
        normalized = " ".join(lesson.split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            rejected.append({"lesson": normalized, "reason": "duplicate"})
            continue
        seen.add(key)
        reason = reject_reason(normalized)
        if reason:
            rejected.append({"lesson": normalized, "reason": reason})
        else:
            accepted.append(normalized)
    return accepted, rejected


def candidate_for(repo_root: Path, lessons: list[str]) -> dict[str, Any]:
    agents_path = repo_root / "AGENTS.md"
    existing_text = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    accepted, rejected = classify_lessons(lessons)
    has_sejong_guidance = "King Sejong" in existing_text or "BEGIN King Sejong" in existing_text
    action = "refresh" if agents_path.exists() else "create"
    if has_sejong_guidance and not accepted:
        recommendation = "no_change"
    elif has_sejong_guidance:
        recommendation = "append_reviewed_lessons"
    else:
        recommendation = "add_sejong_context_block"
    lesson_block = "\n".join(f"- {lesson}" for lesson in accepted)
    candidate_block = DEFAULT_SECTION if not accepted else f"{DEFAULT_SECTION}\n\n## Candidate Durable Lessons\n\n{lesson_block}"
    return {
        "format": "sejong.repo-context-candidate/v0.1-draft",
        "repo_root": str(repo_root.resolve()),
        "target_file": str(agents_path.resolve()),
        "action": action,
        "recommendation": recommendation,
        "has_existing_agents_md": agents_path.exists(),
        "has_existing_sejong_guidance": has_sejong_guidance,
        "accepted_lessons": accepted,
        "rejected_lessons": rejected,
        "candidate_block": candidate_block,
        "write_policy": "read_only_candidate; apply only after explicit user approval or explicit apply instruction",
    }


def render_markdown(candidate: dict[str, Any]) -> str:
    lines = [
        "# Repo Context Candidate",
        "",
        f"- repo_root: {candidate['repo_root']}",
        f"- target_file: {candidate['target_file']}",
        f"- action: {candidate['action']}",
        f"- recommendation: {candidate['recommendation']}",
        f"- write_policy: {candidate['write_policy']}",
        "",
        "## Accepted Lessons",
    ]
    if candidate["accepted_lessons"]:
        lines.extend(f"- {lesson}" for lesson in candidate["accepted_lessons"])
    else:
        lines.append("- none")
    lines.extend(["", "## Rejected Lessons"])
    if candidate["rejected_lessons"]:
        lines.extend(f"- {item['lesson']} ({item['reason']})" for item in candidate["rejected_lessons"])
    else:
        lines.append("- none")
    lines.extend(["", "## Candidate Block", "", "```markdown", candidate["candidate_block"], "```"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a read-only King Sejong AGENTS.md candidate.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--lesson", action="append", default=[], help="Durable lesson to consider for AGENTS.md.")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    candidate = candidate_for(Path(args.repo_root).expanduser(), args.lesson)
    if args.json:
        print(json.dumps(candidate, indent=2, sort_keys=True))
    else:
        print(render_markdown(candidate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
