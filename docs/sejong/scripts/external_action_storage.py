from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Final, TypeAlias

from external_action_contract import (
    FORMAT,
    HASH_PATTERN,
    IDEMPOTENCY_PATTERN,
    ActionIntent,
    ActionStatus,
    Approval,
    ApprovalAuthority,
    Ledger,
    Receipt,
    ReceiptError,
    ensure_safe,
    format_timestamp,
    parse_timestamp,
    validate_ledger,
)


JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
LEDGER_FIELDS: Final = frozenset({"format", "run_id", "updated_at", "receipts"})
RECEIPT_FIELDS: Final = frozenset(
    {
        "action_id",
        "action_name",
        "target_description",
        "input_sha256",
        "action_sha256",
        "idempotency_key",
        "approval",
        "status",
        "dispatched_at",
        "terminal_at",
        "evidence_refs",
    }
)
APPROVAL_FIELDS: Final = frozenset(
    {
        "approval_record_ref",
        "approval_record_sha256",
        "run_id",
        "action_sha256",
        "issuer_authority",
        "issued_at",
        "expires_at",
        "source_user_decision_ref",
    }
)
APPROVAL_RECORD_FIELDS: Final = frozenset(
    {"run_id", "action_sha256", "issuer_authority", "issued_at", "expires_at", "source_user_decision_ref"}
)


def load_approval_record(path: Path) -> Approval:
    absolute = Path(os.path.abspath(path.expanduser()))
    ensure_safe("approval_record_ref", str(absolute))
    if absolute.is_symlink():
        raise ReceiptError(f"approval record path is a symlink: {absolute}")
    try:
        mode = absolute.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ReceiptError(f"approval record must be a regular file: {absolute}")
        raw_bytes = absolute.read_bytes()
    except FileNotFoundError as exc:
        raise ReceiptError(f"missing approval record: {absolute}") from exc
    try:
        loaded: JsonValue = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=reject_duplicate_pairs)
    except UnicodeDecodeError as exc:
        raise ReceiptError("approval record must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ReceiptError(f"invalid approval record JSON: {exc}") from exc
    raw = expect_object(loaded, "approval record")
    ensure_exact_fields(raw, APPROVAL_RECORD_FIELDS, "approval record")
    try:
        authority = ApprovalAuthority(expect_str(raw, "issuer_authority"))
    except ValueError as exc:
        raise ReceiptError("issuer_authority must be host or user") from exc
    return Approval(
        approval_record_ref=str(absolute),
        approval_record_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        run_id=ensure_safe("approval run_id", expect_str(raw, "run_id")),
        action_sha256=expect_hash(raw, "action_sha256"),
        issuer_authority=authority,
        issued_at=parse_timestamp(expect_str(raw, "issued_at"), "issued_at"),
        expires_at=parse_timestamp(expect_str(raw, "expires_at"), "expires_at"),
        source_user_decision_ref=ensure_safe(
            "source_user_decision_ref",
            expect_str(raw, "source_user_decision_ref"),
        ),
    )


def load_ledger(path: Path) -> Ledger:
    try:
        loaded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReceiptError(f"missing ledger: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReceiptError(f"invalid ledger JSON: {exc}") from exc
    raw = expect_object(loaded, "ledger")
    ensure_exact_fields(raw, LEDGER_FIELDS, "ledger")
    if expect_str(raw, "format") != FORMAT:
        raise ReceiptError("unexpected external-action receipt format")
    receipts = tuple(parse_receipt(expect_object(item, "receipt")) for item in expect_list(raw, "receipts"))
    ledger = Ledger(
        run_id=ensure_safe("run_id", expect_str(raw, "run_id")),
        updated_at=parse_timestamp(expect_str(raw, "updated_at"), "updated_at"),
        receipts=receipts,
    )
    validate_ledger(ledger)
    return ledger


def parse_receipt(raw: JsonObject) -> Receipt:
    ensure_exact_fields(raw, RECEIPT_FIELDS, "receipt")
    approval_raw = expect_object(raw.get("approval"), "approval")
    ensure_exact_fields(approval_raw, APPROVAL_FIELDS, "approval")
    intent = ActionIntent(
        ensure_safe("action_id", expect_str(raw, "action_id")),
        ensure_safe("action_name", expect_str(raw, "action_name")),
        ensure_safe("target_description", expect_str(raw, "target_description")),
        expect_hash(raw, "input_sha256"),
        expect_idempotency_key(raw),
    )
    try:
        status = ActionStatus(expect_str(raw, "status"))
    except ValueError as exc:
        raise ReceiptError("invalid external action status") from exc
    evidence_refs = tuple(ensure_safe("evidence ref", item) for item in expect_string_list(raw, "evidence_refs"))
    return Receipt(
        intent=intent,
        action_sha256=expect_hash(raw, "action_sha256"),
        approval=Approval(
            ensure_safe("approval_record_ref", expect_str(approval_raw, "approval_record_ref")),
            expect_hash(approval_raw, "approval_record_sha256"),
            ensure_safe("approval run_id", expect_str(approval_raw, "run_id")),
            expect_hash(approval_raw, "action_sha256"),
            parse_approval_authority(approval_raw),
            parse_timestamp(expect_str(approval_raw, "issued_at"), "issued_at"),
            parse_timestamp(expect_str(approval_raw, "expires_at"), "expires_at"),
            ensure_safe(
                "source_user_decision_ref",
                expect_str(approval_raw, "source_user_decision_ref"),
            ),
        ),
        status=status,
        dispatched_at=expect_optional_timestamp(raw, "dispatched_at"),
        terminal_at=expect_optional_timestamp(raw, "terminal_at"),
        evidence_refs=evidence_refs,
    )


def write_ledger(path: Path, ledger: Ledger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: JsonObject = {
        "format": FORMAT,
        "run_id": ledger.run_id,
        "updated_at": format_timestamp(ledger.updated_at),
        "receipts": [receipt_json(receipt) for receipt in ledger.receipts],
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def receipt_json(receipt: Receipt) -> JsonObject:
    return {
        "action_id": receipt.intent.action_id,
        "action_name": receipt.intent.action_name,
        "target_description": receipt.intent.target_description,
        "input_sha256": receipt.intent.input_sha256,
        "action_sha256": receipt.action_sha256,
        "idempotency_key": receipt.intent.idempotency_key,
        "approval": {
            "approval_record_ref": receipt.approval.approval_record_ref,
            "approval_record_sha256": receipt.approval.approval_record_sha256,
            "run_id": receipt.approval.run_id,
            "action_sha256": receipt.approval.action_sha256,
            "issuer_authority": receipt.approval.issuer_authority.value,
            "issued_at": format_timestamp(receipt.approval.issued_at),
            "expires_at": format_timestamp(receipt.approval.expires_at),
            "source_user_decision_ref": receipt.approval.source_user_decision_ref,
        },
        "status": receipt.status.value,
        "dispatched_at": format_timestamp(receipt.dispatched_at) if receipt.dispatched_at is not None else None,
        "terminal_at": format_timestamp(receipt.terminal_at) if receipt.terminal_at is not None else None,
        "evidence_refs": list(receipt.evidence_refs),
    }


def expect_object(value: JsonValue, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ReceiptError(f"{field} must be an object")
    return value


def ensure_exact_fields(raw: JsonObject, expected: frozenset[str], field: str) -> None:
    unexpected = sorted(set(raw) - expected)
    if unexpected:
        raise ReceiptError(f"unexpected {field} fields: {', '.join(unexpected)}")
    missing = sorted(expected - set(raw))
    if missing:
        raise ReceiptError(f"missing {field} fields: {', '.join(missing)}")


def expect_list(raw: JsonObject, field: str) -> list[JsonValue]:
    value = raw.get(field)
    if not isinstance(value, list):
        raise ReceiptError(f"{field} must be a list")
    return value


def expect_string_list(raw: JsonObject, field: str) -> list[str]:
    values = expect_list(raw, field)
    if not all(isinstance(value, str) for value in values):
        raise ReceiptError(f"{field} must contain only strings")
    return [value for value in values if isinstance(value, str)]


def expect_str(raw: JsonObject, field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str):
        raise ReceiptError(f"{field} must be a string")
    return value


def expect_hash(raw: JsonObject, field: str) -> str:
    value = expect_str(raw, field)
    if HASH_PATTERN.fullmatch(value) is None:
        raise ReceiptError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def expect_idempotency_key(raw: JsonObject) -> str:
    value = expect_str(raw, "idempotency_key")
    if IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        raise ReceiptError("idempotency_key has an invalid format")
    return value


def expect_optional_timestamp(raw: JsonObject, field: str) -> datetime | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReceiptError(f"{field} must be a date-time or null")
    return parse_timestamp(value, field)


def parse_approval_authority(raw: JsonObject) -> ApprovalAuthority:
    try:
        return ApprovalAuthority(expect_str(raw, "issuer_authority"))
    except ValueError as exc:
        raise ReceiptError("issuer_authority must be host or user") from exc


def reject_duplicate_pairs(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    parsed: JsonObject = {}
    for key, value in pairs:
        if key in parsed:
            raise ReceiptError(f"duplicate approval record field: {key}")
        parsed[key] = value
    return parsed
