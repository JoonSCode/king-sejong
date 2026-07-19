from __future__ import annotations

import re
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from discord_contract_types import ControlContractError, JsonObject, SandboxMode


DISPATCH_FIELDS = frozenset({
    "format", "ticket_id", "candidate_sha256", "producer_run_id", "producer_actor_id",
    "reviewer_run_id", "reviewer_actor_id", "reviewer_lane", "reviewer_model", "sandbox",
    "shadow", "write_paths", "canonical_state_write", "authority", "dispatch_sha256",
})
RECEIPT_FIELDS = frozenset({
    "format", "ticket_id", "candidate_sha256", "producer_run_id", "producer_actor_id",
    "reviewer_run_id", "reviewer_actor_id", "reviewer_lane", "shadow", "verdict",
    "evidence_refs", "satisfied_requirements", "unknowns", "authority", "dispatch_sha256",
    "receipt_sha256",
})


class ReviewerLane(StrEnum):
    SOL = "sol"
    ANTIGRAVITY = "antigravity"


class ReviewVerdict(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"


class CandidateEvidenceState(StrEnum):
    REVIEW_PENDING = "review_pending"
    REVIEW_APPROVED = "review_approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReviewDispatchSpec:
    ticket_id: str
    candidate_sha256: str
    producer_run_id: str
    producer_actor_id: str
    reviewer_run_id: str
    reviewer_actor_id: str
    reviewer_lane: ReviewerLane
    reviewer_model: str
    sandbox: SandboxMode
    shadow: bool


def _authority(lane: ReviewerLane) -> str:
    match lane:
        case ReviewerLane.SOL:
            return "approval_recommendation_only"
        case ReviewerLane.ANTIGRAVITY:
            return "shadow_second_opinion_only"
        case unreachable:
            assert_never(unreachable)


def _seal(payload: JsonObject) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def _text_array(value: object, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ControlContractError("invalid_review_receipt", f"{field} must be a string array")
    if not allow_empty and not value:
        raise ControlContractError("invalid_review_receipt", f"{field} must not be empty")
    return tuple(item for item in value if isinstance(item, str))


def _validate_dispatch(dispatch: JsonObject) -> None:
    if set(dispatch) != DISPATCH_FIELDS:
        raise ControlContractError("invalid_review_dispatch", "review dispatch fields differ")
    unsigned = dict(dispatch)
    supplied = unsigned.pop("dispatch_sha256")
    expected = _seal(unsigned)
    lane = dispatch.get("reviewer_lane")
    shadow = dispatch.get("shadow")
    authority = dispatch.get("authority")
    reviewer_model = dispatch.get("reviewer_model")
    expected_authority = (
        "approval_recommendation_only" if lane == ReviewerLane.SOL.value
        else "shadow_second_opinion_only"
    )
    valid = (
        supplied == expected
        and dispatch.get("format") == "sejong.candidate-review-dispatch/v0.1-draft"
        and dispatch.get("producer_run_id") != dispatch.get("reviewer_run_id")
        and dispatch.get("producer_actor_id") != dispatch.get("reviewer_actor_id")
        and dispatch.get("sandbox") == "read-only"
        and isinstance(reviewer_model, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", reviewer_model) is not None
        and dispatch.get("write_paths") == []
        and dispatch.get("canonical_state_write") is False
        and lane in {ReviewerLane.SOL.value, ReviewerLane.ANTIGRAVITY.value}
        and shadow is (lane == ReviewerLane.ANTIGRAVITY.value)
        and authority == expected_authority
    )
    if not valid:
        raise ControlContractError("invalid_review_dispatch", "review dispatch seal or authority differs")


def build_review_dispatch(spec: ReviewDispatchSpec) -> JsonObject:
    if not re.fullmatch(r"[0-9a-f]{64}", spec.candidate_sha256):
        raise ControlContractError("invalid_candidate", "review requires a lowercase SHA-256 candidate hash")
    if (
        spec.producer_run_id == spec.reviewer_run_id
        or spec.producer_actor_id == spec.reviewer_actor_id
    ):
        raise ControlContractError("self_review_forbidden", "producer cannot approve its own candidate")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", spec.reviewer_model) is None:
        raise ControlContractError("unsafe_model", "reviewer model must be one opaque argv-safe token")
    if spec.sandbox is not SandboxMode.READ_ONLY:
        raise ControlContractError("review_must_be_read_only", "review runs cannot request write access")
    if spec.reviewer_lane is ReviewerLane.SOL and spec.shadow:
        raise ControlContractError("invalid_review_lane", "Sol is the canonical independent review lane")
    if spec.reviewer_lane is ReviewerLane.ANTIGRAVITY and not spec.shadow:
        raise ControlContractError("shadow_required", "Antigravity is second-opinion shadow only")
    dispatch: JsonObject = {
        "format": "sejong.candidate-review-dispatch/v0.1-draft",
        "ticket_id": spec.ticket_id,
        "candidate_sha256": spec.candidate_sha256,
        "producer_run_id": spec.producer_run_id,
        "producer_actor_id": spec.producer_actor_id,
        "reviewer_run_id": spec.reviewer_run_id,
        "reviewer_actor_id": spec.reviewer_actor_id,
        "reviewer_lane": spec.reviewer_lane.value,
        "reviewer_model": spec.reviewer_model,
        "sandbox": spec.sandbox.value,
        "shadow": spec.shadow,
        "write_paths": [],
        "canonical_state_write": False,
        "authority": _authority(spec.reviewer_lane),
    }
    dispatch["dispatch_sha256"] = _seal(dispatch)
    return dispatch


def review_receipt(
    dispatch: JsonObject,
    verdict: ReviewVerdict,
    *,
    evidence_refs: tuple[str, ...],
    satisfied_requirements: tuple[str, ...],
    unknowns: tuple[str, ...],
) -> JsonObject:
    _validate_dispatch(dispatch)
    if not evidence_refs or any(not item for item in evidence_refs):
        raise ControlContractError("invalid_review_receipt", "review receipt requires evidence references")
    receipt: JsonObject = {
        "format": "sejong.candidate-review-receipt/v0.1-draft",
        "ticket_id": dispatch["ticket_id"],
        "candidate_sha256": dispatch["candidate_sha256"],
        "producer_run_id": dispatch["producer_run_id"],
        "producer_actor_id": dispatch["producer_actor_id"],
        "reviewer_run_id": dispatch["reviewer_run_id"],
        "reviewer_actor_id": dispatch["reviewer_actor_id"],
        "reviewer_lane": dispatch["reviewer_lane"],
        "shadow": dispatch["shadow"],
        "verdict": verdict.value,
        "evidence_refs": list(evidence_refs),
        "satisfied_requirements": list(satisfied_requirements),
        "unknowns": list(unknowns),
        "authority": dispatch["authority"],
        "dispatch_sha256": dispatch["dispatch_sha256"],
    }
    receipt["receipt_sha256"] = _seal(receipt)
    return receipt


def _validate_receipt(receipt: JsonObject) -> None:
    if set(receipt) != RECEIPT_FIELDS:
        raise ControlContractError("invalid_review_receipt", "review receipt fields differ")
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256")
    lane = receipt.get("reviewer_lane")
    valid = (
        supplied == _seal(unsigned)
        and receipt.get("format") == "sejong.candidate-review-receipt/v0.1-draft"
        and receipt.get("producer_run_id") != receipt.get("reviewer_run_id")
        and receipt.get("producer_actor_id") != receipt.get("reviewer_actor_id")
        and lane in {ReviewerLane.SOL.value, ReviewerLane.ANTIGRAVITY.value}
        and receipt.get("shadow") is (lane == ReviewerLane.ANTIGRAVITY.value)
        and receipt.get("authority") == (
            "approval_recommendation_only" if lane == ReviewerLane.SOL.value
            else "shadow_second_opinion_only"
        )
        and receipt.get("verdict") in {item.value for item in ReviewVerdict}
    )
    _text_array(receipt.get("evidence_refs"), "evidence_refs", allow_empty=False)
    _text_array(receipt.get("satisfied_requirements"), "satisfied_requirements", allow_empty=True)
    _text_array(receipt.get("unknowns"), "unknowns", allow_empty=True)
    if not valid:
        raise ControlContractError("invalid_review_receipt", "review receipt seal or authority differs")


def evaluate_candidate(
    candidate_sha256: str,
    receipts: tuple[JsonObject, ...],
    verification_requirements: tuple[str, ...],
) -> CandidateEvidenceState:
    for receipt in receipts:
        _validate_receipt(receipt)
    sol = tuple(
        item
        for item in receipts
        if item.get("reviewer_lane") == ReviewerLane.SOL.value
        and item.get("shadow") is False
        and item.get("candidate_sha256") == candidate_sha256
    )
    if any(item.get("verdict") == ReviewVerdict.CHANGES_REQUESTED.value for item in sol):
        return CandidateEvidenceState.CHANGES_REQUESTED
    if any(item.get("verdict") == ReviewVerdict.BLOCKED.value for item in sol):
        return CandidateEvidenceState.BLOCKED
    approved = tuple(item for item in sol if item.get("verdict") == ReviewVerdict.APPROVED.value)
    for item in approved:
        satisfied = item.get("satisfied_requirements")
        evidence = item.get("evidence_refs")
        unknowns = item.get("unknowns")
        if (
            isinstance(satisfied, list)
            and set(verification_requirements).issubset(set(value for value in satisfied if isinstance(value, str)))
            and isinstance(evidence, list)
            and any(isinstance(value, str) and value for value in evidence)
            and unknowns == []
        ):
            return CandidateEvidenceState.REVIEW_APPROVED
    return CandidateEvidenceState.REVIEW_PENDING
