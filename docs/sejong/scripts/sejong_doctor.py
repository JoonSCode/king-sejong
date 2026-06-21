#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import site
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]

REQUIRED_SOURCE_PATHS = (
    "AGENTS.md",
    ".agents/skills/sejong/SKILL.md",
    ".agents/skills/jangyeongsil/SKILL.md",
    ".agents/skills/jiphyeonjeon/SKILL.md",
    ".agents/skills/uigwe/SKILL.md",
    ".agents/skills/seungjeongwon/SKILL.md",
    ".agents/skills/why-gate/SKILL.md",
    "docs/sejong/ROUTER.md",
    "docs/sejong/PROTOCOL.md",
    "docs/sejong/SEUNGJEONGWON_EXECUTOR.md",
    "docs/sejong/WORKFLOW_RUN.md",
    "plugins/king-sejong/.codex-plugin/plugin.json",
    "plugins/king-sejong/hooks/hooks.json",
    "scripts/install-sejong.sh",
)

PYTHON_DEPENDENCIES = (
    (
        "jsonschema",
        "Required by docs/sejong/scripts/validate_json_contracts.py.",
        "Use `uv run --with jsonschema --with referencing python3 docs/sejong/scripts/validate_json_contracts.py` or install jsonschema and referencing in the active Python.",
    ),
    (
        "referencing",
        "Required by docs/sejong/scripts/validate_json_contracts.py.",
        "Use `uv run --with jsonschema --with referencing python3 docs/sejong/scripts/validate_json_contracts.py` or install jsonschema and referencing in the active Python.",
    ),
)


@dataclass
class Check:
    name: str
    status: str
    detail: str
    hint: str = ""


def add_user_site() -> None:
    try:
        user_site = site.getusersitepackages()
    except Exception:
        return
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)


def module_available(name: str) -> bool:
    add_user_site()
    return importlib.util.find_spec(name) is not None


def sejong_home() -> Path:
    if os.environ.get("SEJONG_HOME"):
        return Path(os.environ["SEJONG_HOME"]).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "sejong"


def source_path_checks(repo_root: Path) -> list[Check]:
    missing = [path for path in REQUIRED_SOURCE_PATHS if not (repo_root / path).exists()]
    if missing:
        return [
            Check(
                "source-managed-paths",
                "fail",
                "missing managed source paths: " + ", ".join(missing),
                "Run from the King Sejong source checkout or refresh the checkout.",
            )
        ]
    return [Check("source-managed-paths", "ok", "all managed source paths are present")]


def plugin_manifest_check(repo_root: Path) -> list[Check]:
    manifest_path = repo_root / "plugins/king-sejong/.codex-plugin/plugin.json"
    hooks_path = repo_root / "plugins/king-sejong/hooks/hooks.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [Check("plugin-adapter-json", "fail", f"plugin adapter JSON is unreadable: {exc}")]
    plugin_name = manifest.get("name")
    if plugin_name != "king-sejong":
        return [Check("plugin-adapter-json", "fail", f"unexpected plugin name: {plugin_name!r}")]
    if not isinstance(hooks, dict):
        return [Check("plugin-adapter-json", "fail", "hooks.json must be a JSON object")]
    return [Check("plugin-adapter-json", "ok", "plugin manifest and hook metadata are readable")]


def dependency_checks(skip: bool) -> list[Check]:
    if skip:
        return [Check("python-dependencies", "warn", "python dependency check skipped")]
    checks: list[Check] = []
    for module_name, detail, hint in PYTHON_DEPENDENCIES:
        if module_available(module_name):
            checks.append(Check(f"python-dependency:{module_name}", "ok", detail))
        else:
            checks.append(Check(f"python-dependency:{module_name}", "fail", f"missing module: {module_name}. {detail}", hint))
    return checks


def git_check(repo_root: Path) -> list[Check]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--short"],
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception as exc:
        return [Check("git-status", "warn", f"could not inspect git status: {exc}")]
    if result.returncode != 0:
        return [Check("git-status", "warn", result.stderr.strip() or "git status failed")]
    if result.stdout.strip():
        return [Check("git-status", "warn", "source checkout has uncommitted changes")]
    return [Check("git-status", "ok", "source checkout is clean")]


def load_hook_module() -> Any:
    scripts_path = str(SEJONG_ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    import king_sejong_hooks

    return king_sejong_hooks


def active_context_check(context_path: Path | None) -> list[Check]:
    hooks = load_hook_module()
    resolved_path = context_path or hooks.resolve_context_path(None)
    if not resolved_path.exists():
        return [
            Check(
                "active-context",
                "warn",
                f"active context not found: {resolved_path}",
                "Run user-scope install or pass --context when checking a specific runtime context.",
            )
        ]
    try:
        context = json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [Check("active-context", "fail", f"active context is unreadable: {exc}")]
    missing = hooks.missing_context_fields(context)
    if missing:
        return [Check("active-context", "fail", "active context missing fields: " + ", ".join(missing))]
    if not hooks.context_is_well_formed(context):
        return [Check("active-context", "fail", "active context is not well formed")]
    active_runs = hooks.active_seungjeongwon_run_summaries(context)
    if active_runs:
        return [Check("active-context", "warn", "active Seungjeongwon runs: " + "; ".join(active_runs))]
    return [Check("active-context", "ok", f"active context is well formed: {resolved_path}")]


def run_checks(args: argparse.Namespace) -> list[Check]:
    repo_root = Path(args.repo_root).expanduser().resolve()
    checks: list[Check] = []
    checks.extend(source_path_checks(repo_root))
    checks.extend(plugin_manifest_check(repo_root))
    checks.extend(dependency_checks(args.skip_python_deps))
    checks.extend(git_check(repo_root))
    if not args.skip_active_context:
        checks.extend(active_context_check(Path(args.context).expanduser() if args.context else None))
    return checks


def render_text(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        line = f"[{check.status}] {check.name}: {check.detail}"
        if check.hint:
            line += f" hint={check.hint}"
        lines.append(line)
    return "\n".join(lines)


def exit_code(checks: list[Check]) -> int:
    return 1 if any(check.status == "fail" for check in checks) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only King Sejong health check.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--context", help="Specific active context checkpoint to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable check results.")
    parser.add_argument("--skip-python-deps", action="store_true", help="Skip environment-specific Python module checks.")
    parser.add_argument("--skip-active-context", action="store_true", help="Skip runtime active-context inspection.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    checks = run_checks(args)
    if args.json:
        print(json.dumps({"format": "sejong.doctor-result/v0.1-draft", "sejong_home": str(sejong_home()), "checks": [asdict(check) for check in checks]}, indent=2, sort_keys=True))
    else:
        print(render_text(checks))
    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
