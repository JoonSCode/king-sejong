from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def path_key(path: str | Path) -> str:
    value = str(resolve_path(path))
    if sys.platform == "darwin":
        return value.casefold()
    return value


def identity_path_digest(path: str | Path) -> str:
    """Hash exact canonical path bytes without platform-wide case folding."""
    canonical = str(resolve_path(path))
    return hashlib.sha256(os.fsencode(canonical)).hexdigest()


def paths_equal(left: str | Path, right: str | Path) -> bool:
    try:
        return Path(left).expanduser().samefile(Path(right).expanduser())
    except OSError:
        return path_key(left) == path_key(right)


def path_contains_or_equals(child: str | Path, root: str | Path) -> bool:
    child_path = resolve_path(child)
    root_path = resolve_path(root)
    try:
        child_path.relative_to(root_path)
        return True
    except ValueError:
        child_key = Path(path_key(child_path))
        root_key = Path(path_key(root_path))
        try:
            child_key.relative_to(root_key)
            return True
        except ValueError:
            return child_key == root_key


def git_common_dir(path: str | Path) -> Path | None:
    candidate = resolve_path(path)
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        dot_git = directory / ".git"
        if dot_git.is_dir():
            return dot_git.resolve()
        if not dot_git.is_file():
            continue
        try:
            marker = dot_git.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None
        prefix = "gitdir:"
        if not marker.lower().startswith(prefix):
            return None
        git_dir = Path(marker[len(prefix) :].strip())
        if not git_dir.is_absolute():
            git_dir = dot_git.parent / git_dir
        git_dir = git_dir.resolve()
        common_marker = git_dir / "commondir"
        if not common_marker.is_file():
            return git_dir
        try:
            common_value = common_marker.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None
        common_dir = Path(common_value)
        if not common_dir.is_absolute():
            common_dir = git_dir / common_dir
        return common_dir.resolve()
    return None


def repo_identity(path: str | Path) -> str:
    resolved = resolve_path(path)
    common_dir = git_common_dir(resolved)
    identity_path = common_dir if common_dir is not None else resolved
    identity_kind = "git" if common_dir is not None else "path"
    digest = identity_path_digest(identity_path)
    return f"{identity_kind}:{digest}"


def declared_repo_identity(path: str | Path) -> str:
    resolved = resolve_path(path)
    if (resolved / ".git").exists():
        return repo_identity(resolved)
    digest = identity_path_digest(resolved)
    return f"path:{digest}"
