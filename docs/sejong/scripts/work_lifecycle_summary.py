from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


WORK_EVENT_FORMAT = "sejong.work-event/v0.1-draft"
LESSON_CANDIDATE_FORMAT = "sejong.lesson-candidate/v0.1-draft"
RESOURCE_LEASE_FORMAT = "sejong.worker-resource-lease/v0.1-draft"
CLEANUP_RECEIPT_FORMAT = "sejong.worker-cleanup-receipt/v0.1-draft"


class ArtifactData(TypedDict, total=False):
    format: str
    event_id: str
    candidate_id: str
    lease_id: str
    resource_lease_id: str
    cleanup_status: str


class CleanupEvidence(TypedDict):
    lease_count: int
    receipt_count: int
    status_counts: dict[str, int]
    proof_complete: bool
    gaps: list[str]


class LifecycleSummary(TypedDict):
    event_count: int
    lesson_candidate_count: int
    event_ledger_refs: list[str]
    lesson_candidate_refs: list[str]
    cleanup_evidence: CleanupEvidence


@dataclass(frozen=True, slots=True)
class LifecycleSummaryError(Exception):
    path: Path
    detail: str

    def __str__(self) -> str:
        return f"invalid lifecycle artifact {self.path}: {self.detail}"


def load_artifact(path: Path) -> ArtifactData:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LifecycleSummaryError(path, str(error)) from error


def load_event_ledger(path: Path) -> tuple[ArtifactData, ...]:
    events: list[ArtifactData] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise LifecycleSummaryError(path, f"line {line_number}: {error}") from error
    return tuple(events)


def relative_refs(run_dir: Path, paths: tuple[Path, ...]) -> list[str]:
    return [str(path.relative_to(run_dir)) for path in paths]


def build_lifecycle_summary(run_dir: Path) -> LifecycleSummary:
    event_ledgers = tuple(sorted(run_dir.rglob("work-events*.jsonl")))
    candidate_paths = tuple(sorted(run_dir.rglob("lesson-candidate*.json")))
    lease_paths = tuple(sorted(run_dir.rglob("*worker-resource-lease*.json")))
    receipt_paths = tuple(sorted(run_dir.rglob("*worker-cleanup-receipt*.json")))

    events = tuple(event for path in event_ledgers for event in load_event_ledger(path))
    candidates = tuple(load_artifact(path) for path in candidate_paths)
    leases = tuple(load_artifact(path) for path in lease_paths)
    receipts = tuple(load_artifact(path) for path in receipt_paths)

    if any(event.get("format") != WORK_EVENT_FORMAT for event in events):
        raise LifecycleSummaryError(run_dir, "work event format mismatch")
    if any(candidate.get("format") != LESSON_CANDIDATE_FORMAT for candidate in candidates):
        raise LifecycleSummaryError(run_dir, "lesson candidate format mismatch")
    if any(lease.get("format") != RESOURCE_LEASE_FORMAT for lease in leases):
        raise LifecycleSummaryError(run_dir, "worker resource lease format mismatch")
    if any(receipt.get("format") != CLEANUP_RECEIPT_FORMAT for receipt in receipts):
        raise LifecycleSummaryError(run_dir, "worker cleanup receipt format mismatch")

    lease_ids = sorted(str(lease.get("lease_id", "")) for lease in leases)
    released_ids = {
        str(receipt.get("resource_lease_id", ""))
        for receipt in receipts
        if receipt.get("cleanup_status") == "released"
    }
    status_counts: dict[str, int] = {}
    for receipt in receipts:
        status = str(receipt.get("cleanup_status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    gaps = [lease_id for lease_id in lease_ids if lease_id not in released_ids]

    return {
        "event_count": len(events),
        "lesson_candidate_count": len(candidates),
        "event_ledger_refs": relative_refs(run_dir, event_ledgers),
        "lesson_candidate_refs": relative_refs(run_dir, candidate_paths),
        "cleanup_evidence": {
            "lease_count": len(leases),
            "receipt_count": len(receipts),
            "status_counts": status_counts,
            "proof_complete": not gaps,
            "gaps": gaps,
        },
    }
