from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from discord_contract_types import ControlContractError, JsonObject, TicketIntent


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    argv: tuple[str, ...]
    exit_code: int
    output_ref: str


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    path: Path
    artifact_format: str
    verification_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateHandoffSpec:
    sejong_home: Path
    ticket: TicketIntent
    producer_run_id: str
    workspace: Path
    base_commit: str
    head_commit: str
    dirty_before: bool
    dirty_after: bool
    diff_bytes: bytes
    commands: tuple[CommandEvidence, ...]
    artifacts: tuple[ArtifactInput, ...]
    unknowns: tuple[str, ...]
    next_run_constraints: tuple[str, ...]

    @property
    def run_dir(self) -> Path:
        return self.sejong_home / "runs" / "discord" / self.ticket.ticket_id


@dataclass(frozen=True, slots=True)
class CandidateHandoffResult:
    handoff_path: Path
    manifest_path: Path
    candidate_sha256: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: JsonObject) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _serialized(payload: JsonObject) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _write_exclusive(path: Path, payload: JsonObject) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ControlContractError("immutable_handoff_exists", f"sealed artifact already exists: {path.name}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_serialized(payload))


def _artifact_record(item: ArtifactInput) -> JsonObject:
    try:
        content = item.path.read_bytes()
    except OSError as exc:
        raise ControlContractError("invalid_evidence", f"cannot read artifact: {item.path}") from exc
    return {
        "ref": str(item.path),
        "sha256": _sha256(content),
        "size_bytes": len(content),
        "artifact_format": item.artifact_format,
        "producer": "codex-ticket-runner",
        "verification_refs": list(item.verification_refs),
    }


def _manifest(spec: CandidateHandoffSpec, generated_at: str) -> JsonObject:
    commands: list[JsonObject] = []
    for command in spec.commands:
        if not command.argv or any(not item for item in command.argv):
            raise ControlContractError("invalid_evidence", "command evidence requires structured non-empty argv")
        commands.append({
            "argv": list(command.argv),
            "exit_code": command.exit_code,
            "output_ref": command.output_ref,
        })
    return {
        "format": "sejong.evidence-manifest/v0.1-draft",
        "manifest_id": f"discord-ticket-{spec.ticket.ticket_id}",
        "run_id": spec.producer_run_id,
        "ticket_id": spec.ticket.ticket_id,
        "repo_root": str(spec.workspace),
        "generated_at": generated_at,
        "producer": {
            "surface": "codex-ticket-runner",
            "model": spec.ticket.model,
            "sandbox": spec.ticket.sandbox.value,
        },
        "parent_event_refs": [spec.ticket.ticket_id],
        "commands": commands,
        "artifacts": [_artifact_record(item) for item in spec.artifacts],
    }


def write_candidate_handoff(spec: CandidateHandoffSpec) -> CandidateHandoffResult:
    commit_pattern = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
    if (
        not spec.sejong_home.is_absolute()
        or not spec.workspace.is_absolute()
        or re.fullmatch(commit_pattern, spec.base_commit) is None
        or re.fullmatch(commit_pattern, spec.head_commit) is None
    ):
        raise ControlContractError("invalid_handoff", "handoff requires absolute runtime/workspace and exact git commits")
    if not spec.commands or not spec.artifacts:
        raise ControlContractError("invalid_evidence", "candidate requires command and artifact evidence")
    spec.run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest_path = spec.run_dir / "evidence-manifest.json"
    handoff_path = spec.run_dir / "candidate-handoff.json"
    if manifest_path.exists() or handoff_path.exists():
        raise ControlContractError("immutable_handoff_exists", "candidate handoff artifacts are sealed")
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest = _manifest(spec, generated_at)
    manifest_sha256 = _sha256(_serialized(manifest))
    handoff: JsonObject = {
        "format": "sejong.codex-candidate-handoff/v0.1-draft",
        "ticket_id": spec.ticket.ticket_id,
        "producer_run_id": spec.producer_run_id,
        "authority": "evidence_only",
        "completion_eligible": False,
        "workspace": {
            "path": str(spec.workspace),
            "base_commit": spec.base_commit,
            "head_commit": spec.head_commit,
            "dirty_before": spec.dirty_before,
            "dirty_after": spec.dirty_after,
            "diff_sha256": _sha256(spec.diff_bytes),
        },
        "producer": {"model": spec.ticket.model, "sandbox": spec.ticket.sandbox.value},
        "evidence_manifest_ref": str(manifest_path),
        "evidence_manifest_sha256": manifest_sha256,
        "unknowns": list(spec.unknowns),
        "verification_requirements": list(spec.ticket.verification_requirements),
        "next_run_constraints": list(spec.next_run_constraints),
        "created_at": generated_at,
    }
    candidate_sha256 = _sha256(_canonical(handoff))
    handoff["candidate_sha256"] = candidate_sha256
    _write_exclusive(manifest_path, manifest)
    _write_exclusive(handoff_path, handoff)
    return CandidateHandoffResult(handoff_path, manifest_path, candidate_sha256)
