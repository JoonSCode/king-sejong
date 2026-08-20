#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
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
INSTALL_TRANSACTION_FORMAT: Final = "king-sejong.install-transaction/v0.1"
RUNTIME_AUTHORITY_EPOCH: Final = 2


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def runtime_authority_files(root: Path) -> tuple[tuple[str, Path], ...]:
    scripts = root / "skills" / "sejong" / "docs" / "scripts"
    plugin_root = Path(__file__).resolve().parent
    return (
        ("canonical-hook", scripts / "king_sejong_hooks.py"),
        ("context", scripts / "sejong_context.py"),
        ("session-binding", scripts / "sejong_session_binding.py"),
        ("paths", scripts / "sejong_paths.py"),
        ("runtime-lock", scripts / "sejong_runtime_lock.py"),
        ("plugin-runner", Path(__file__).resolve()),
        ("plugin-hooks", plugin_root / "hooks.json"),
    )


def runtime_authority_digest(files: tuple[tuple[str, Path], ...]) -> str:
    digest = hashlib.sha256()
    for label, path in files:
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def install_generation_error(root: Path) -> str | None:
    transaction_path = root / "sejong" / "state" / "install-transaction.json"
    try:
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError) as error:
        return f"install transaction unavailable: {type(error).__name__}: {error}"
    if not isinstance(transaction, dict):
        return "install transaction must be an object"
    if transaction.get("format") != INSTALL_TRANSACTION_FORMAT:
        return "install transaction format mismatch"
    if transaction.get("status") != "complete":
        return f"install transaction status is {transaction.get('status')!r}"
    if transaction.get("runtime_authority_epoch") != RUNTIME_AUTHORITY_EPOCH:
        return "runtime authority epoch mismatch"
    if transaction.get("minimum_runtime_authority_epoch") != RUNTIME_AUTHORITY_EPOCH:
        return "minimum runtime authority epoch mismatch"
    expected_digest = transaction.get("runtime_authority_sha256")
    if not isinstance(expected_digest, str) or not expected_digest:
        return "runtime authority digest is missing"
    try:
        actual_digest = runtime_authority_digest(runtime_authority_files(root))
    except OSError as error:
        return f"runtime authority files unavailable: {type(error).__name__}: {error}"
    if actual_digest != expected_digest:
        return "runtime authority digest mismatch"
    return None


def main() -> int:
    event_name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not event_name:
        return 0

    root = codex_home()
    hook_script = root / "skills" / "sejong" / "docs" / "scripts" / "king_sejong_hooks.py"
    if not hook_script.exists():
        if event_name in PROTECTED_EVENTS:
            print(f"missing King Sejong canonical hook script: {hook_script}", file=sys.stderr)
            return 127
        return 0

    generation_error = install_generation_error(root)
    if generation_error is not None:
        if event_name in PROTECTED_EVENTS:
            print(f"King Sejong install generation is not ready: {generation_error}", file=sys.stderr)
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
