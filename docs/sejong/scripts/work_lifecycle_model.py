from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic_core import PydanticCustomError


WORK_EVENT_FORMAT: Final = "sejong.work-event/v0.1-draft"
LESSON_CANDIDATE_FORMAT: Final = "sejong.lesson-candidate/v0.1-draft"
SOURCE_EVIDENCE_POLICY: Final = "structured_sanitized_refs_only"
_PRIVATE_PATH = re.compile(r"(?<![A-Za-z0-9])(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)")
_SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{12,}|api[_-]?key\\s*[:=])")
NonEmptyString = Annotated[str, StringConstraints(min_length=1)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class EventType(StrEnum):
    USER_INTERVENTION = "user_intervention"
    ASSISTANT_ERROR_CANDIDATE = "assistant_error_candidate"
    TOOL_ENVIRONMENT_FAILURE = "tool_environment_failure"
    PROJECT_DEFECT = "project_defect"
    PREFERENCE_CHANGE = "preference_change"
    CLEANUP_OUTCOME = "cleanup_outcome"


class EpistemicStatus(StrEnum):
    KNOWN = "known"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


def safe_text(value: str) -> str:
    if _PRIVATE_PATH.search(value):
        raise PydanticCustomError("private_absolute_path", "private absolute path is forbidden")
    if _SECRET.search(value):
        raise PydanticCustomError("secret_material", "secret-like material is forbidden")
    return value


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: NonEmptyString
    sha256: Sha256

    @field_validator("ref")
    @classmethod
    def ref_is_sanitized(cls, value: str) -> str:
        if value.startswith(("/", "~")) or re.match(r"^[A-Za-z]:\\\\", value):
            raise PydanticCustomError("private_absolute_path", "private absolute path is forbidden")
        return safe_text(value)


class Privacy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_evidence_copied: Literal[False]
    contains_secret: Literal[False]
    contains_private_absolute_path: Literal[False]


class WorkEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["sejong.work-event/v0.1-draft"]
    event_id: NonEmptyString
    occurred_at: datetime
    run_id: NonEmptyString
    repo_id: NonEmptyString
    task_class: NonEmptyString
    event_type: EventType
    epistemic_status: EpistemicStatus
    pattern_key: NonEmptyString
    summary: NonEmptyString
    response: NonEmptyString
    outcome: NonEmptyString
    source_refs: Annotated[tuple[SourceRef, ...], Field(min_length=1)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    privacy: Privacy

    @field_validator(
        "event_id",
        "run_id",
        "repo_id",
        "task_class",
        "pattern_key",
        "summary",
        "response",
        "outcome",
    )
    @classmethod
    def text_is_sanitized(cls, value: str) -> str:
        return safe_text(value)


class LessonCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["sejong.lesson-candidate/v0.1-draft"]
    candidate_id: NonEmptyString
    generated_at: datetime
    pattern_key: NonEmptyString
    event_refs: Annotated[tuple[NonEmptyString, ...], Field(min_length=2)]
    source_digests: Annotated[tuple[Sha256, ...], Field(min_length=2)]
    independent_run_ids: Annotated[tuple[NonEmptyString, ...], Field(min_length=2)]
    occurrence_count: Annotated[int, Field(ge=2)]
    recommended_response: NonEmptyString
    verification: Literal["manual_review_required"]
    status: Literal["candidate"]
    activation_authority: Literal["none"]
    source_evidence_policy: Literal["structured_sanitized_refs_only"]


@dataclass(frozen=True, slots=True)
class LifecycleError(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def canonical_event_digest(event: WorkEvent) -> str:
    payload = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def derive_candidate(events: tuple[WorkEvent, ...], pattern_key: str) -> LessonCandidate:
    matching = tuple(sorted((event for event in events if event.pattern_key == pattern_key), key=lambda item: (item.occurred_at, item.event_id)))
    run_ids = tuple(sorted({event.run_id for event in matching}))
    if len(run_ids) < 2:
        raise LifecycleError("insufficient_independent_runs", "lesson candidates require two independent runs")
    digests = tuple(canonical_event_digest(event) for event in matching)
    identity = hashlib.sha256(f"{pattern_key}|{'|'.join(digests)}".encode()).hexdigest()[:20]
    return LessonCandidate(
        format=LESSON_CANDIDATE_FORMAT,
        candidate_id=f"lesson-{identity}",
        generated_at=max(event.occurred_at for event in matching),
        pattern_key=pattern_key,
        event_refs=tuple(f"work-event://{event.event_id}" for event in matching),
        source_digests=digests,
        independent_run_ids=run_ids,
        occurrence_count=len(matching),
        recommended_response=matching[-1].response,
        verification="manual_review_required",
        status="candidate",
        activation_authority="none",
        source_evidence_policy=SOURCE_EVIDENCE_POLICY,
    )
