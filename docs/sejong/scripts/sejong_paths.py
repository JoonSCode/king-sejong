from __future__ import annotations

import sys
from pathlib import Path


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def path_key(path: str | Path) -> str:
    value = str(resolve_path(path))
    if sys.platform == "darwin":
        return value.casefold()
    return value


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
