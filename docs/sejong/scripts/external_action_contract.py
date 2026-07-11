from __future__ import annotations

# noqa: SIZE_OK - the cohesive external-action state machine keeps transition and approval invariants together.

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Final, TypeAlias, assert_never


FORMAT: Final = "sejong.external-action-receipts/v0.1-draft"
HASH_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
IDEMPOTENCY_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_APPROVAL_WINDOW: Final = timedelta(hours=1)
MAX_APPROVAL_RECORD_AGE: Final = timedelta(minutes=5)
SENSITIVE_PATTERN: Final = re.compile(
    r"(?:bearer\s+\S+|(?:password|secret|access[_-]?token|api[_-]?key|authorization)\s*[:=]\s*\S+|(?:^|[?&\s])token\s*=|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ActionStatus(StrEnum):
    AUTHORIZED = "authorized"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalAuthority(StrEnum):
    HOST = "host"
    USER = "user"


@dataclass(frozen=True, slots=True)
class ReceiptError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class Approval:
    approval_record_ref: str
    approval_record_sha256: str
    run_id: str
    action_sha256: str
    issuer_authority: ApprovalAuthority
    issued_at: datetime
    expires_at: datetime
    source_user_decision_ref: str


@dataclass(frozen=True, slots=True)
class ActionIntent:
    action_id: str
    action_name: str
    target_description: str
    input_sha256: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class Receipt:
    intent: ActionIntent
    action_sha256: str
    approval: Approval
    status: ActionStatus
    dispatched_at: datetime | None
    terminal_at: datetime | None
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Ledger:
    run_id: str
    updated_at: datetime
    receipts: tuple[Receipt, ...]


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    run_id: str
    intent: ActionIntent
    approval: Approval
    at: datetime


@dataclass(frozen=True, slots=True)
class RecordRequest:
    action_id: str
    status: ActionStatus
    at: datetime
    evidence_refs: tuple[str, ...]


def parse_timestamp(raw: str, field: str) -> datetime:
    normalized = f"{raw[:-1]}+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ReceiptError(f"invalid {field}: expected ISO 8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ReceiptError(f"invalid {field}: timezone is required")
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_safe(field: str, value: str) -> str:
    if not value.strip():
        raise ReceiptError(f"{field} must be non-empty")
    if len(value) > 2048:
        raise ReceiptError(f"{field} exceeds 2048 characters")
    if SENSITIVE_PATTERN.search(value) is not None:
        raise ReceiptError(f"unsafe {field}: credentials or raw secrets are forbidden")
    return value


def action_sha256(intent: ActionIntent) -> str:
    canonical: JsonObject = {
        "action_id": intent.action_id,
        "action_name": intent.action_name,
        "idempotency_key": intent.idempotency_key,
        "input_sha256": intent.input_sha256,
        "target_description": intent.target_description,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def authorize(ledger: Ledger | None, request: AuthorizationRequest) -> Ledger:
    validate_authorization_request(request)
    current = ledger or Ledger(request.run_id, request.at, ())
    if current.run_id != request.run_id:
        raise ReceiptError(f"run_id mismatch: ledger={current.run_id} request={request.run_id}")
    for receipt in current.receipts:
        if receipt.intent.action_id == request.intent.action_id:
            raise ReceiptError(f"duplicate action_id: {request.intent.action_id}")
        if receipt.intent.idempotency_key == request.intent.idempotency_key:
            match receipt.status:
                case ActionStatus.COMPLETED:
                    raise ReceiptError(f"completed idempotency key already exists: {request.intent.idempotency_key}")
                case ActionStatus.AUTHORIZED | ActionStatus.DISPATCHED | ActionStatus.FAILED | ActionStatus.CANCELLED:
                    raise ReceiptError(f"duplicate idempotency key already exists: {request.intent.idempotency_key}")
                case unreachable:
                    assert_never(unreachable)
    computed_hash = action_sha256(request.intent)
    if request.approval.action_sha256 != computed_hash:
        raise ReceiptError("approval action hash does not match the canonical action hash")
    receipt = Receipt(request.intent, computed_hash, request.approval, ActionStatus.AUTHORIZED, None, None, ())
    return Ledger(current.run_id, request.at, (*current.receipts, receipt))


def record(ledger: Ledger, request: RecordRequest) -> Ledger:
    ensure_safe_refs(request.evidence_refs)
    updated: list[Receipt] = []
    matched = False
    for receipt in ledger.receipts:
        if receipt.intent.action_id != request.action_id:
            updated.append(receipt)
            continue
        matched = True
        updated.append(transition(receipt, request))
    if not matched:
        raise ReceiptError(f"unknown action_id: {request.action_id}")
    return Ledger(ledger.run_id, request.at, tuple(updated))


def transition(receipt: Receipt, request: RecordRequest) -> Receipt:
    allowed = {
        (ActionStatus.AUTHORIZED, ActionStatus.DISPATCHED),
        (ActionStatus.AUTHORIZED, ActionStatus.CANCELLED),
        (ActionStatus.DISPATCHED, ActionStatus.COMPLETED),
        (ActionStatus.DISPATCHED, ActionStatus.FAILED),
    }
    if (receipt.status, request.status) not in allowed:
        raise ReceiptError(f"invalid transition: {receipt.status.value} -> {request.status.value}")
    validate_approval(receipt)
    if request.status is ActionStatus.DISPATCHED:
        if request.at < receipt.approval.issued_at:
            raise ReceiptError("dispatch time is before approval")
        if request.at > receipt.approval.expires_at:
            raise ReceiptError("approval expired before dispatch")
    if request.status in {ActionStatus.COMPLETED, ActionStatus.FAILED}:
        match receipt.dispatched_at:
            case datetime() as dispatched_at:
                if request.at < dispatched_at:
                    raise ReceiptError("terminal time is before dispatch")
            case None:
                raise ReceiptError("terminal state requires a dispatch time")
            case unreachable:
                assert_never(unreachable)
    evidence = tuple(dict.fromkeys((*receipt.evidence_refs, *request.evidence_refs)))
    match request.status:
        case ActionStatus.DISPATCHED:
            return replace(receipt, status=request.status, dispatched_at=request.at, evidence_refs=evidence)
        case ActionStatus.COMPLETED | ActionStatus.FAILED | ActionStatus.CANCELLED:
            return replace(receipt, status=request.status, terminal_at=request.at, evidence_refs=evidence)
        case ActionStatus.AUTHORIZED:
            raise ReceiptError("authorized is not a recordable transition")
        case unreachable:
            assert_never(unreachable)


def validate_authorization_request(request: AuthorizationRequest) -> None:
    ensure_safe("run_id", request.run_id)
    ensure_safe("action_id", request.intent.action_id)
    ensure_safe("action_name", request.intent.action_name)
    ensure_safe("target_description", request.intent.target_description)
    ensure_safe("approval_record_ref", request.approval.approval_record_ref)
    ensure_safe("approval run_id", request.approval.run_id)
    ensure_safe("source_user_decision_ref", request.approval.source_user_decision_ref)
    if HASH_PATTERN.fullmatch(request.intent.input_sha256) is None:
        raise ReceiptError("input_sha256 must be a lowercase SHA-256 hex digest")
    if IDEMPOTENCY_PATTERN.fullmatch(request.intent.idempotency_key) is None:
        raise ReceiptError("idempotency_key has an invalid format")
    if HASH_PATTERN.fullmatch(request.approval.approval_record_sha256) is None:
        raise ReceiptError("approval_record_sha256 must be a lowercase SHA-256 hex digest")
    if request.approval.run_id != request.run_id:
        raise ReceiptError("approval run_id does not match the authorization run_id")
    if request.approval.expires_at <= request.approval.issued_at:
        raise ReceiptError("approval expiry must be after approval time")
    if request.approval.expires_at - request.approval.issued_at > MAX_APPROVAL_WINDOW:
        raise ReceiptError("approval window exceeds one hour")
    if request.at < request.approval.issued_at:
        raise ReceiptError("approval record is not yet valid")
    if request.at > request.approval.expires_at:
        raise ReceiptError("approval record has expired")
    if request.at - request.approval.issued_at > MAX_APPROVAL_RECORD_AGE:
        raise ReceiptError("approval record is stale or backdated")


def validate_approval(receipt: Receipt) -> None:
    ensure_safe("approval_record_ref", receipt.approval.approval_record_ref)
    ensure_safe("approval run_id", receipt.approval.run_id)
    ensure_safe("source_user_decision_ref", receipt.approval.source_user_decision_ref)
    if HASH_PATTERN.fullmatch(receipt.approval.approval_record_sha256) is None:
        raise ReceiptError("approval_record_sha256 must be a lowercase SHA-256 hex digest")
    if receipt.approval.action_sha256 != receipt.action_sha256:
        raise ReceiptError("approval action hash does not match receipt action hash")
    if receipt.approval.expires_at <= receipt.approval.issued_at:
        raise ReceiptError("approval expiry must be after approval time")
    if receipt.approval.expires_at - receipt.approval.issued_at > MAX_APPROVAL_WINDOW:
        raise ReceiptError("approval window exceeds one hour")
    if action_sha256(receipt.intent) != receipt.action_sha256:
        raise ReceiptError("canonical action hash does not match receipt action hash")


def ensure_safe_refs(refs: tuple[str, ...]) -> None:
    for ref in refs:
        ensure_safe("evidence ref", ref)


def validate_ledger(ledger: Ledger) -> None:
    action_ids: set[str] = set()
    keys: set[str] = set()
    for receipt in ledger.receipts:
        validate_approval(receipt)
        if receipt.approval.run_id != ledger.run_id:
            raise ReceiptError("approval run_id does not match ledger run_id")
        if receipt.intent.action_id in action_ids:
            raise ReceiptError(f"duplicate action_id: {receipt.intent.action_id}")
        if receipt.intent.idempotency_key in keys:
            raise ReceiptError(f"duplicate idempotency key already exists: {receipt.intent.idempotency_key}")
        action_ids.add(receipt.intent.action_id)
        keys.add(receipt.intent.idempotency_key)
        validate_receipt_timestamps(receipt)


def validate_receipt_timestamps(receipt: Receipt) -> None:
    dispatched_at = receipt.dispatched_at
    terminal_at = receipt.terminal_at
    issued_at = receipt.approval.issued_at
    expires_at = receipt.approval.expires_at
    match receipt.status:
        case ActionStatus.AUTHORIZED:
            if dispatched_at is not None or terminal_at is not None:
                raise ReceiptError("authorized receipt cannot have dispatch or terminal timestamps")
        case ActionStatus.DISPATCHED:
            if dispatched_at is None or terminal_at is not None:
                raise ReceiptError("dispatched receipt requires only dispatched_at")
            if dispatched_at < issued_at or dispatched_at > expires_at:
                raise ReceiptError("dispatched_at must be inside the approval window")
        case ActionStatus.COMPLETED | ActionStatus.FAILED:
            if dispatched_at is None or terminal_at is None:
                raise ReceiptError("completed or failed receipt requires dispatch and terminal timestamps")
            if dispatched_at < issued_at or dispatched_at > expires_at:
                raise ReceiptError("dispatched_at must be inside the approval window")
            if terminal_at < dispatched_at:
                raise ReceiptError("terminal time is before dispatch")
        case ActionStatus.CANCELLED:
            if dispatched_at is not None or terminal_at is None:
                raise ReceiptError("cancelled receipt requires only terminal_at")
            if terminal_at < issued_at:
                raise ReceiptError("cancelled time is before approval")
        case unreachable:
            assert_never(unreachable)
