#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
POLICY_DEFAULTS = SEJONG_ROOT / "policy.defaults.json"
RUN_SUMMARY_FORMAT = "sejong.run-summary/v0.1-draft"
RUN_STATUSES = {"success", "failed", "blocked"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sejong_home() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def runs_root() -> Path:
    return sejong_home() / "runs"


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or POLICY_DEFAULTS
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    retention = data["artifact_retention"]
    return retention["profiles"][retention["default_profile"]]


def resolve_under_runs(path: str | Path) -> Path:
    run_dir = Path(path).expanduser().resolve()
    root = runs_root().resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"refusing path outside Sejong runs root: {run_dir}") from exc
    return run_dir


def run_identity(run_dir: Path) -> tuple[str, str]:
    relative = run_dir.resolve().relative_to(runs_root().resolve())
    if len(relative.parts) < 2:
        raise SystemExit(f"run directory must be under runs/<repo-id>/<run-id>: {run_dir}")
    return relative.parts[0], relative.parts[1]


def active_context() -> dict[str, Any] | None:
    path = sejong_home() / "state" / "active-context.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def path_contains_or_equals(child: Path, root: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return child.resolve() == root.resolve()


def is_active_run(run_dir: Path) -> bool:
    context = active_context()
    if not context:
        return False
    repo_id, run_id = run_identity(run_dir)
    if context.get("repo_id") == repo_id and context.get("run_id") == run_id:
        return True
    for ref in context.get("artifact_refs") or []:
        ref_path = Path(ref).expanduser()
        if not ref_path.is_absolute():
            ref_path = sejong_home() / ref_path
        if path_contains_or_equals(ref_path, run_dir):
            return True
    return False


def has_promoted_marker(run_dir: Path, policy: dict[str, Any]) -> bool:
    return any((run_dir / name).exists() for name in policy["promoted_marker_names"])


def relative_to_run(run_dir: Path, path: Path) -> str:
    return str(path.relative_to(run_dir))


def path_size(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file() or child.is_symlink():
            total += child.stat().st_size
    return total


def classify_children(run_dir: Path, policy: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    keep_names = set(policy["compact_keep_names"]) | set(policy["promoted_marker_names"])
    kept: list[Path] = []
    prunable: list[Path] = []
    for child in sorted(run_dir.iterdir(), key=lambda item: item.name):
        if child.name in keep_names:
            kept.append(child)
        else:
            prunable.append(child)
    return kept, prunable


def delete_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_run_summary(
    *,
    run_dir: Path,
    status: str,
    policy: dict[str, Any],
    execute: bool,
    reason: str,
    allow_raw_prune: bool,
) -> tuple[dict[str, Any], int]:
    if status not in RUN_STATUSES:
        raise SystemExit(f"unsupported run status: {status}")
    if not run_dir.exists() or not run_dir.is_dir():
        raise SystemExit(f"missing run directory: {run_dir}")

    run_dir = resolve_under_runs(run_dir)
    repo_id, run_id = run_identity(run_dir)
    active = is_active_run(run_dir)
    promoted = has_promoted_marker(run_dir, policy)
    kept, prunable = classify_children(run_dir, policy)
    prunable_sizes = {relative_to_run(run_dir, path): path_size(path) for path in prunable}
    kept_sizes = {relative_to_run(run_dir, path): path_size(path) for path in kept}
    destructive_requested = execute and allow_raw_prune and bool(prunable)
    failures: list[str] = []
    deleted: list[str] = []
    would_delete: list[str] = []
    retained: list[dict[str, str]] = []

    if active and destructive_requested:
        failures.append("active run is protected from cleanup")
    if promoted and destructive_requested:
        failures.append("promoted run is protected from cleanup")

    can_delete = destructive_requested and not failures
    for path in prunable:
        rel_path = relative_to_run(run_dir, path)
        if not allow_raw_prune:
            retained.append({"path": rel_path, "reason": "status retention window keeps raw artifacts"})
        elif active:
            retained.append({"path": rel_path, "reason": "active run"})
        elif promoted:
            retained.append({"path": rel_path, "reason": "promoted run"})
        elif execute:
            delete_path(path)
            deleted.append(rel_path)
        else:
            would_delete.append(rel_path)

    for path in kept:
        retained.append({"path": relative_to_run(run_dir, path), "reason": "compact or protected artifact"})

    summary = {
        "format": RUN_SUMMARY_FORMAT,
        "repo_id": repo_id,
        "run_id": run_id,
        "status": status,
        "generated_at": now_utc(),
        "run_dir": str(run_dir),
        "dry_run": not execute,
        "reason": reason,
        "policy": {
            "success_raw_ttl_days": policy["success_raw_ttl_days"],
            "failed_raw_ttl_days": policy["failed_raw_ttl_days"],
            "blocked_raw_ttl_days": policy["blocked_raw_ttl_days"],
            "compact_ttl_days": policy["compact_ttl_days"],
            "max_compact_runs_per_repo": policy["max_compact_runs_per_repo"],
        },
        "protection": {
            "active_run": active,
            "promoted_run": promoted,
        },
        "actions": {
            "deleted": deleted,
            "would_delete": would_delete,
            "retained": retained,
            "failures": failures,
        },
        "bytes": {
            "deleted": sum(prunable_sizes[path] for path in deleted),
            "would_delete": sum(prunable_sizes[path] for path in would_delete),
            "retained": sum(kept_sizes.values())
            + sum(prunable_sizes[item["path"]] for item in retained if item["path"] in prunable_sizes),
        },
    }
    write_json(run_dir / "run-summary.json", summary)
    return summary, 1 if failures else 0


def read_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "run-summary.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def age_days(path: Path) -> float:
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 86400


def status_allows_raw_prune(status: str, age: float, policy: dict[str, Any], *, finalize: bool) -> bool:
    if status == "success":
        return finalize or age >= policy["success_raw_ttl_days"]
    if status == "failed":
        return age >= policy["failed_raw_ttl_days"]
    if status == "blocked":
        return age >= policy["blocked_raw_ttl_days"]
    return False


def iter_run_dirs(root: Path) -> list[Path]:
    root = root.expanduser().resolve()
    if not root.exists():
        return []
    return [path for path in sorted(root.glob("*/*")) if path.is_dir()]


def finalize_run(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy).expanduser() if args.policy else None)
    run_dir = resolve_under_runs(args.run_dir)
    summary, status = build_run_summary(
        run_dir=run_dir,
        status=args.status,
        policy=policy,
        execute=args.execute,
        reason="finalize-run",
        allow_raw_prune=args.status == "success",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return status


def prune_runs(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy).expanduser() if args.policy else None)
    root = Path(args.runs_root).expanduser() if args.runs_root else runs_root()
    root = root.resolve()
    if root != runs_root().resolve():
        try:
            root.relative_to(runs_root().resolve())
        except ValueError as exc:
            raise SystemExit(f"refusing runs root outside Sejong runs root: {root}") from exc

    run_dirs = iter_run_dirs(root)
    newest_by_repo: dict[str, list[Path]] = {}
    for run_dir in run_dirs:
        repo_id, _ = run_identity(run_dir)
        newest_by_repo.setdefault(repo_id, []).append(run_dir)
    for repo_runs in newest_by_repo.values():
        repo_runs.sort(key=lambda item: item.stat().st_mtime, reverse=True)

    results: list[dict[str, Any]] = []
    failures = 0
    for run_dir in run_dirs:
        summary = read_summary(run_dir)
        status = str(summary.get("status")) if summary else "unknown"
        repo_id, _ = run_identity(run_dir)
        repo_rank = newest_by_repo[repo_id].index(run_dir)
        active = is_active_run(run_dir)
        promoted = has_promoted_marker(run_dir, policy)
        compact_expired = age_days(run_dir) >= policy["compact_ttl_days"]
        compact_over_limit = repo_rank >= policy["max_compact_runs_per_repo"]

        if status not in RUN_STATUSES:
            results.append({"run_dir": str(run_dir), "action": "skip", "reason": "missing or unsupported run-summary status"})
            continue
        if active:
            results.append({"run_dir": str(run_dir), "action": "skip", "reason": "active run"})
            continue
        if promoted:
            results.append({"run_dir": str(run_dir), "action": "skip", "reason": "promoted run"})
            continue

        if compact_expired and compact_over_limit:
            if args.execute:
                shutil.rmtree(run_dir)
                results.append({"run_dir": str(run_dir), "action": "deleted_run"})
            else:
                results.append({"run_dir": str(run_dir), "action": "would_delete_run"})
            continue

        allow_raw_prune = status_allows_raw_prune(status, age_days(run_dir), policy, finalize=False)
        run_summary, result_status = build_run_summary(
            run_dir=run_dir,
            status=status,
            policy=policy,
            execute=args.execute,
            reason="prune-runs",
            allow_raw_prune=allow_raw_prune,
        )
        failures += result_status
        results.append({"run_dir": str(run_dir), "action": "raw_prune_checked", "summary": run_summary["actions"]})

    report = {
        "format": "sejong.cleanup-report/v0.1-draft",
        "generated_at": now_utc(),
        "dry_run": not args.execute,
        "runs_root": str(root),
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


def report_runs(args: argparse.Namespace) -> int:
    root = Path(args.runs_root).expanduser() if args.runs_root else runs_root()
    run_dirs = iter_run_dirs(root)
    report = {
        "format": "sejong.cleanup-inventory/v0.1-draft",
        "generated_at": now_utc(),
        "runs_root": str(root),
        "run_count": len(run_dirs),
        "runs": [
            {
                "path": str(run_dir),
                "bytes": path_size(run_dir),
                "active": is_active_run(run_dir),
                "summary_status": (read_summary(run_dir) or {}).get("status"),
            }
            for run_dir in run_dirs
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compact and prune external King Sejong runtime artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    finalize = subparsers.add_parser("finalize-run", help="Compact one run and prune successful raw artifacts.")
    finalize.add_argument("run_dir")
    finalize.add_argument("--status", choices=sorted(RUN_STATUSES), required=True)
    finalize.add_argument("--policy")
    finalize.add_argument("--execute", action="store_true", help="Delete prunable artifacts. Omit for dry-run.")
    finalize.set_defaults(func=finalize_run)

    prune = subparsers.add_parser("prune-runs", help="Apply retention policy across Sejong run directories.")
    prune.add_argument("runs_root", nargs="?")
    prune.add_argument("--policy")
    prune.add_argument("--execute", action="store_true", help="Delete prunable artifacts. Omit for dry-run.")
    prune.set_defaults(func=prune_runs)

    report = subparsers.add_parser("report", help="Inventory Sejong run directories without deleting anything.")
    report.add_argument("runs_root", nargs="?")
    report.set_defaults(func=report_runs)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
