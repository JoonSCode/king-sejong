from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from candidate_review import CandidateEvidenceState
from discord_contract_types import ControlContractError, JsonObject


class TicketState(StrEnum):
    REVIEW_PENDING = "review_pending"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"
    FINAL_VERIFICATION_PENDING = "final_verification_pending"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class CoreVerification:
    candidate_sha256: str
    verifier_run_id: str
    satisfied_requirements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    passed: bool


def _preverification_state(review: CandidateEvidenceState) -> TicketState:
    match review:
        case CandidateEvidenceState.REVIEW_PENDING:
            return TicketState.REVIEW_PENDING
        case CandidateEvidenceState.CHANGES_REQUESTED:
            return TicketState.CHANGES_REQUESTED
        case CandidateEvidenceState.BLOCKED:
            return TicketState.BLOCKED
        case CandidateEvidenceState.REVIEW_APPROVED:
            return TicketState.FINAL_VERIFICATION_PENDING
        case unreachable:
            assert_never(unreachable)


def reduce_ticket_state(
    candidate_sha256: str,
    review_state: CandidateEvidenceState,
    requirements: tuple[str, ...],
    verification: CoreVerification | None,
) -> JsonObject:
    if re.fullmatch(r"[0-9a-f]{64}", candidate_sha256) is None:
        raise ControlContractError("invalid_candidate", "ticket state requires a SHA-256 candidate")
    state = _preverification_state(review_state)
    verification_ref: str | None = None
    if verification is not None:
        if verification.candidate_sha256 != candidate_sha256:
            raise ControlContractError("candidate_mismatch", "Core verification targets another candidate")
        verification_ref = verification.verifier_run_id
        evidence_complete = (
            verification.passed
            and set(requirements).issubset(set(verification.satisfied_requirements))
            and bool(verification.evidence_refs)
        )
        if review_state is CandidateEvidenceState.REVIEW_APPROVED and evidence_complete:
            state = TicketState.VERIFIED
        elif review_state is CandidateEvidenceState.REVIEW_APPROVED and not verification.passed:
            state = TicketState.BLOCKED
    return {
        "format": "sejong.discord-ticket-evidence-state/v0.1-draft",
        "candidate_sha256": candidate_sha256,
        "state": state.value,
        "completion_eligible": state is TicketState.VERIFIED,
        "completion_authority": "core_final_verification",
        "review_state": review_state.value,
        "core_verification_ref": verification_ref,
    }
