#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


PROTECTED_EVENTS = {
    "PermissionRequest",
    "PreCompact",
    "PreToolUse",
    "Stop",
}


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

    os.execvp("python3", ["python3", str(hook_script), event_name])
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
