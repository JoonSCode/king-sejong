#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.11", "typer>=0.16"]
# ///
# ─── How to run ───
# uv run docs/sejong/scripts/work_lifecycle.py --help

from __future__ import annotations

import fcntl
import os
import tempfile
from pathlib import Path
from typing import Never

import typer
from pydantic import ValidationError

from work_lifecycle_model import LifecycleError, WorkEvent, derive_candidate


app = typer.Typer(help="Record sanitized work events and derive review-only lesson candidates.")


def load_event(path: Path) -> WorkEvent:
    return WorkEvent.model_validate_json(path.read_text(encoding="utf-8"))


def load_ledger(path: Path) -> tuple[WorkEvent, ...]:
    if not path.exists():
        return ()
    events: list[WorkEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                events.append(WorkEvent.model_validate_json(line))
            except ValidationError as error:
                raise LifecycleError("invalid_ledger_event", f"{path}:{line_number}: {error}") from error
    return tuple(events)


def fail(error: ValidationError | LifecycleError | OSError) -> Never:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=2)


def write_private_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o600)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


@app.command("record-event")
def record_event(
    event: Path = typer.Option(..., exists=True, dir_okay=False),
    ledger: Path = typer.Option(..., dir_okay=False),
) -> None:
    try:
        parsed = load_event(event)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            existing = tuple(
                WorkEvent.model_validate_json(line)
                for line in handle
                if line.strip()
            )
            if any(item.event_id == parsed.event_id for item in existing):
                raise LifecycleError("duplicate_event_id", parsed.event_id)
            handle.seek(0, os.SEEK_END)
            handle.write(parsed.model_dump_json())
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o600)
        typer.echo(f"event recorded: {parsed.event_id}")
    except (ValidationError, LifecycleError, OSError) as error:
        fail(error)


@app.command("derive-candidate")
def derive_lesson_candidate(
    ledger: Path = typer.Option(..., exists=True, dir_okay=False),
    pattern_key: str = typer.Option(...),
    output: Path = typer.Option(..., dir_okay=False),
) -> None:
    try:
        candidate = derive_candidate(load_ledger(ledger), pattern_key)
        write_private_json(output, candidate.model_dump_json(indent=2))
        typer.echo(f"lesson candidate written: {candidate.candidate_id}")
    except (ValidationError, LifecycleError, OSError) as error:
        fail(error)


if __name__ == "__main__":
    app()
