#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORMAT = "sejong.continuity-replay-gate/v0.1-draft"
SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_hook(event_name: str, context: Path, repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), event_name, "--context", str(context)],
        input=json.dumps({"hook_event_name": event_name, "cwd": str(repo_root)}),
        text=True,
        capture_output=True,
        cwd=str(repo_root),
    )
    if result.returncode != 0:
        return {"error": result.stderr or result.stdout}
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def repo_relative_path(ref: str, context_data: dict[str, Any], repo_root: Path) -> Path:
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path
    context_repo_root = context_data.get("repo_root")
    if isinstance(context_repo_root, str) and context_repo_root:
        root = Path(context_repo_root).expanduser()
        if not root.is_absolute():
            root = repo_root / root
        return root / path
    return repo_root / path


def looks_like_continuity_capsule_ref(ref: str) -> bool:
    lowered = ref.lower()
    return "continuity-capsule" in lowered and lowered.endswith(".json")


def materialize_context_refs(context: Path, repo_root: Path, work_dir: Path) -> Path:
    data = json.loads(context.read_text(encoding="utf-8"))
    changed = False
    materialized_refs: list[Any] = []
    for ref in data.get("artifact_refs") or []:
        if (
            not isinstance(ref, str)
            or Path(ref).expanduser().is_absolute()
            or not looks_like_continuity_capsule_ref(ref)
        ):
            materialized_refs.append(ref)
            continue
        if repo_relative_path(ref, data, repo_root).exists():
            materialized_refs.append(ref)
            continue
        context_relative = context.parent / ref
        if context_relative.exists():
            materialized_refs.append(str(context_relative.resolve()))
            changed = True
        else:
            materialized_refs.append(ref)
    if not changed:
        return context
    data["artifact_refs"] = materialized_refs
    materialized = work_dir / "continuity-replay-context.materialized.json"
    materialized.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return materialized


def check_item(check_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "detail": detail}


def hook_additional_context(output: dict[str, Any]) -> str:
    return str((output.get("hookSpecificOutput") or {}).get("additionalContext") or "")


def judge(args: argparse.Namespace) -> int:
    context = Path(args.context).resolve()
    repo_root = Path(args.repo_root).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        materialized_context = materialize_context_refs(context, repo_root, Path(tmp))
        precompact = run_hook("PreCompact", materialized_context, repo_root)
        postcompact = run_hook("PostCompact", materialized_context, repo_root)
    additional = hook_additional_context(postcompact)

    checks = [
        check_item(
            "precompact_allows_valid_continuity_state",
            precompact.get("continue", True) is not False,
            precompact.get("stopReason") or "valid continuity refs can compact",
        ),
        check_item(
            "postcompact_injects_continuity_capsule_projection",
            "continuity_capsule=" in additional,
            "PostCompact additionalContext contains continuity capsule projection.",
        ),
        check_item(
            "projection_stays_under_budget",
            len(additional) <= args.max_chars,
            f"projection_chars={len(additional)} max_chars={args.max_chars}",
        ),
    ]
    for item in args.require or []:
        checks.append(
            check_item(
                f"required_text_present:{item}",
                item in additional,
                f"required text present in projection: {item}",
            )
        )
    for item in args.forbid or []:
        checks.append(
            check_item(
                f"forbidden_text_absent:{item}",
                item not in additional,
                f"forbidden text absent from projection: {item}",
            )
        )

    passed = all(check["passed"] for check in checks)
    payload = {
        "format": FORMAT,
        "generated_at": now_utc(),
        "context": str(context),
        "repo_root": str(repo_root),
        "passed": passed,
        "projection_chars": len(additional),
        "checks": checks,
        "projection": additional,
    }
    if args.write:
        write_path = Path(args.write)
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify King Sejong continuity projection survives compaction.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    judge_parser = subparsers.add_parser("judge", help="Run PreCompact/PostCompact continuity replay checks.")
    judge_parser.add_argument("--context", required=True)
    judge_parser.add_argument("--repo-root", default=".")
    judge_parser.add_argument("--require", action="append")
    judge_parser.add_argument("--forbid", action="append")
    judge_parser.add_argument("--max-chars", type=int, default=4000)
    judge_parser.add_argument("--write")
    judge_parser.set_defaults(func=judge)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
