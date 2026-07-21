#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Final


PROTECTED_EVENTS = {
    "PermissionRequest",
    "PreCompact",
    "PreToolUse",
    "Stop",
}
REQUIRED_PYTHON: Final = (3, 11)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def main() -> int:
    event_name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not event_name:
        return 0

    hook_script = codex_home() / "skills" / "sejong" / "docs" / "scripts" / "king_sejong_hooks.py"
    if not hook_script.exists():
        if event_name in PROTECTED_EVENTS:
            print(f"missing King Sejong canonical hook script: {hook_script}", file=sys.stderr)
            return 127
        return 0

    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if sys.version_info >= REQUIRED_PYTHON:
        os.execv(sys.executable, [sys.executable, str(hook_script), event_name])

    uv_path = shutil.which("uv")
    if uv_path is not None:
        os.execv(
            uv_path,
            [
                uv_path,
                "run",
                "--python",
                "3.11",
                "--no-project",
                "python",
                str(hook_script),
                event_name,
            ],
        )

    if event_name in PROTECTED_EVENTS:
        print("King Sejong hooks require Python 3.11+ or uv", file=sys.stderr)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
