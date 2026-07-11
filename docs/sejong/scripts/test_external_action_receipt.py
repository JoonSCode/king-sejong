#!/usr/bin/env -S uv run --script
# noqa: SIZE_OK - the assigned single CLI integration surface owns the complete approval security matrix.
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run test_external_action_receipt.py
# 3. Or make executable and run:
#      chmod +x test_external_action_receipt.py && ./test_external_action_receipt.py
# ─────────────────

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeAlias


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ACTION_RECEIPT = SCRIPT_PATH.with_name("external_action_receipt.py")

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class AuthorizationFixture:
    ledger: Path
    payload: Path
    approval_record: Path
    run_id: str = "run-test"
    action_id: str = "action-1"
    action_name: str = "publish-message"
    target_description: str = "sandbox://message/test"
    idempotency_key: str = "publish:test:1"


@dataclass(frozen=True, slots=True)
class ApprovalRecordSpec:
    run_id: str
    action_sha256: str
    issuer_authority: str
    issued_at: str
    expires_at: str
    source_user_decision_ref: str


def run_receipt(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ACTION_RECEIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


def load_json_object(path: Path) -> JsonObject:
    loaded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return loaded


def object_list_field(raw: JsonObject, field: str) -> list[JsonObject]:
    value = raw.get(field)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError(f"expected object list field: {field}")
    return [item for item in value if isinstance(item, dict)]


def object_field(raw: JsonObject, field: str) -> JsonObject:
    value = raw.get(field)
    if not isinstance(value, dict):
        raise AssertionError(f"expected object field: {field}")
    return value


def make_fixture(root: Path, action_id: str = "action-1", key: str = "publish:test:1") -> AuthorizationFixture:
    fixture = AuthorizationFixture(
        ledger=root / "external-actions.json",
        payload=root / f"{action_id}-input.json",
        approval_record=root / f"{action_id}-approval.json",
        action_id=action_id,
        idempotency_key=key,
    )
    fixture.payload.write_text("{}", encoding="utf-8")
    return fixture


def timestamp(delta: timedelta = timedelta()) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat().replace("+00:00", "Z")


def canonical_action_sha256(fixture: AuthorizationFixture) -> str:
    canonical: JsonObject = {
        "action_id": fixture.action_id,
        "action_name": fixture.action_name,
        "idempotency_key": fixture.idempotency_key,
        "input_sha256": hashlib.sha256(fixture.payload.read_bytes()).hexdigest(),
        "target_description": fixture.target_description,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def valid_approval(fixture: AuthorizationFixture) -> ApprovalRecordSpec:
    return ApprovalRecordSpec(
        run_id=fixture.run_id,
        action_sha256=canonical_action_sha256(fixture),
        issuer_authority="user",
        issued_at=timestamp(timedelta(seconds=-1)),
        expires_at=timestamp(timedelta(minutes=30)),
        source_user_decision_ref="user-decision://run-test/decision-1",
    )


def write_approval_record(
    fixture: AuthorizationFixture,
    spec: ApprovalRecordSpec,
    extra_fields: JsonObject | None = None,
) -> None:
    payload: JsonObject = {
        "run_id": spec.run_id,
        "action_sha256": spec.action_sha256,
        "issuer_authority": spec.issuer_authority,
        "issued_at": spec.issued_at,
        "expires_at": spec.expires_at,
        "source_user_decision_ref": spec.source_user_decision_ref,
    }
    if extra_fields is not None:
        payload.update(extra_fields)
    fixture.approval_record.write_text(json.dumps(payload), encoding="utf-8")


def authorize_args(fixture: AuthorizationFixture) -> list[str]:
    return [
        "authorize",
        "--ledger",
        str(fixture.ledger),
        "--run-id",
        fixture.run_id,
        "--action-id",
        fixture.action_id,
        "--action-name",
        fixture.action_name,
        "--target-description",
        fixture.target_description,
        "--input-file",
        str(fixture.payload),
        "--idempotency-key",
        fixture.idempotency_key,
        "--approval-record",
        str(fixture.approval_record),
    ]


def authorize_fixture(fixture: AuthorizationFixture) -> subprocess.CompletedProcess[str]:
    write_approval_record(fixture, valid_approval(fixture))
    return run_receipt(authorize_args(fixture))


class ExternalActionReceiptTests(unittest.TestCase):
    def test_inline_approval_flags_are_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a caller attempts to self-assert approval through the old inline flags.
            fixture = make_fixture(Path(tmp))
            inline_args = authorize_args(fixture)[:-2] + [
                "--approval-ref",
                "user:approval:self-issued",
                "--approved-at",
                timestamp(timedelta(minutes=-1)),
                "--approval-expires-at",
                timestamp(timedelta(minutes=30)),
            ]

            # When: authorization is attempted without a separate approval record.
            completed = run_receipt(inline_args)

            # Then: the worker-authored assertion is rejected before any ledger is written.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--approval-record", completed.stderr)
            self.assertFalse(fixture.ledger.exists())

    def test_authorize_rejects_worker_issuer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approval record claims worker authority.
            fixture = make_fixture(Path(tmp))
            write_approval_record(fixture, replace(valid_approval(fixture), issuer_authority="worker"))

            # When: authorization loads the record.
            completed = run_receipt(authorize_args(fixture))

            # Then: only host or user authority is accepted.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("issuer_authority must be host or user", completed.stderr)

    def test_authorize_rejects_wrong_approval_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approval record is bound to another run.
            fixture = make_fixture(Path(tmp))
            write_approval_record(fixture, replace(valid_approval(fixture), run_id="run-other"))

            # When: authorization loads the record.
            completed = run_receipt(authorize_args(fixture))

            # Then: the run binding is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("approval run_id does not match", completed.stderr)

    def test_authorize_rejects_wrong_approval_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approval record is bound to another canonical action.
            fixture = make_fixture(Path(tmp))
            write_approval_record(fixture, replace(valid_approval(fixture), action_sha256="0" * 64))

            # When: authorization loads the record.
            completed = run_receipt(authorize_args(fixture))

            # Then: the action binding is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("approval action hash does not match", completed.stderr)

    def test_authorize_rejects_stale_backdated_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a still-unexpired approval record was issued too far in the past.
            fixture = make_fixture(Path(tmp))
            spec = replace(
                valid_approval(fixture),
                issued_at=timestamp(timedelta(minutes=-10)),
                expires_at=timestamp(timedelta(minutes=20)),
            )
            write_approval_record(fixture, spec)

            # When: authorization loads the stale/backdated record.
            completed = run_receipt(authorize_args(fixture))

            # Then: freshness validation rejects it.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("stale or backdated", completed.stderr)

    def test_authorize_rejects_expired_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approval record has already expired.
            fixture = make_fixture(Path(tmp))
            spec = replace(
                valid_approval(fixture),
                issued_at=timestamp(timedelta(minutes=-2)),
                expires_at=timestamp(timedelta(minutes=-1)),
            )
            write_approval_record(fixture, spec)

            # When: authorization loads the expired record.
            completed = run_receipt(authorize_args(fixture))

            # Then: current time outside the window is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("approval record has expired", completed.stderr)

    def test_authorize_rejects_unbounded_record_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approval record requests an overlong validity window.
            fixture = make_fixture(Path(tmp))
            spec = replace(valid_approval(fixture), expires_at=timestamp(timedelta(hours=2)))
            write_approval_record(fixture, spec)

            # When: authorization loads the record.
            completed = run_receipt(authorize_args(fixture))

            # Then: the bounded-window contract rejects it.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("approval window exceeds", completed.stderr)

    def test_authorize_rejects_symlink_approval_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: the approval record path is a symbolic link.
            root = Path(tmp)
            fixture = make_fixture(root)
            actual_record = root / "actual-approval.json"
            actual_fixture = replace(fixture, approval_record=actual_record)
            write_approval_record(actual_fixture, valid_approval(fixture))
            fixture.approval_record.symlink_to(actual_record)

            # When: authorization attempts to load the symlink.
            completed = run_receipt(authorize_args(fixture))

            # Then: unsafe indirection is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink", completed.stderr)

    def test_authorize_rejects_unexpected_approval_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a record contains an extra caller-controlled field.
            fixture = make_fixture(Path(tmp))
            write_approval_record(fixture, valid_approval(fixture), {"worker_claim": "approved"})

            # When: authorization strictly parses the record.
            completed = run_receipt(authorize_args(fixture))

            # Then: exact-field validation rejects the record.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unexpected approval record fields", completed.stderr)

    def test_concurrent_duplicate_authorization_writes_one_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: two processes authorize the same action and idempotency key concurrently.
            fixture = make_fixture(Path(tmp))
            write_approval_record(fixture, valid_approval(fixture))
            command = [sys.executable, str(ACTION_RECEIPT), *authorize_args(fixture)]
            processes = [
                subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_ROOT))
                for _ in range(2)
            ]

            # When: both processes complete.
            results: list[tuple[int, str]] = []
            for process in processes:
                _, stderr = process.communicate()
                results.append((process.returncode, stderr))

            # Then: the lock serializes the writes and the duplicate is rejected.
            self.assertEqual(sorted(code for code, _ in results), [0, 1], results)
            self.assertTrue(any("duplicate action_id" in stderr for _, stderr in results), results)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            self.assertEqual(len(receipts), 1)

    def test_authorize_records_hashes_without_raw_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an approved no-side-effect action and sensitive raw input.
            fixture = make_fixture(Path(tmp))
            fixture.payload.write_text('{"api_key":"secret-value","message":"hello"}', encoding="utf-8")
            write_approval_record(fixture, valid_approval(fixture))
            approval_bytes = fixture.approval_record.read_bytes()

            # When: the action is authorized through the CLI.
            completed = run_receipt(authorize_args(fixture))

            # Then: the receipt stores only deterministic hashes and approval metadata.
            self.assertEqual(completed.returncode, 0, completed.stderr)
            raw_ledger = fixture.ledger.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", raw_ledger)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            self.assertEqual(receipt["input_sha256"], hashlib.sha256(fixture.payload.read_bytes()).hexdigest())
            self.assertEqual(receipt["status"], "authorized")
            approval = object_field(receipt, "approval")
            self.assertEqual(approval["approval_record_ref"], str(fixture.approval_record))
            self.assertEqual(approval["approval_record_sha256"], hashlib.sha256(approval_bytes).hexdigest())
            self.assertEqual(run_receipt(["check", str(fixture.ledger)]).returncode, 0)

    def test_dispatch_rejects_missing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a receipt whose required approval was tampered away.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            approval = object_field(receipt, "approval")
            approval["approval_record_ref"] = ""
            fixture.ledger.write_text(json.dumps(data), encoding="utf-8")

            # When: dispatch is attempted.
            completed = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "dispatched", "--at", timestamp()]
            )

            # Then: the invalid approval prevents the external-action state change.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("approval", completed.stderr)

    def test_dispatch_rejects_stale_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an action whose approval validity window has elapsed.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)

            # When: dispatch is attempted after approval expiry.
            completed = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "dispatched", "--at", timestamp(timedelta(minutes=31))]
            )

            # Then: the stale approval is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("expired", completed.stderr)

    def test_completed_idempotency_key_cannot_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: one approved action reached completed terminal state.
            root = Path(tmp)
            fixture = make_fixture(root)
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            dispatched = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "dispatched", "--at", timestamp()]
            )
            self.assertEqual(dispatched.returncode, 0, dispatched.stderr)
            finished = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "completed", "--at", timestamp(timedelta(seconds=1)), "--evidence-ref", "sillok://run-test/event-1"]
            )
            self.assertEqual(finished.returncode, 0, finished.stderr)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            self.assertEqual(receipt["evidence_refs"], ["sillok://run-test/event-1"])

            # When: a second action attempts to reuse the completed key.
            duplicate_fixture = replace(
                make_fixture(root, action_id="action-2"),
                ledger=fixture.ledger,
            )
            duplicate = authorize_fixture(duplicate_fixture)

            # Then: duplicate execution is deterministically rejected.
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("completed idempotency key", duplicate.stderr)

    def test_secret_bearing_evidence_ref_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an authorized action and a credential-bearing evidence string.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            before = fixture.ledger.read_bytes()

            # When: dispatch tries to store the unsafe evidence string.
            completed = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "dispatched", "--at", timestamp(), "--evidence-ref", "https://example.test/?token=supersecret"]
            )

            # Then: the unsafe ref is rejected and the ledger stays unchanged.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unsafe evidence ref", completed.stderr)
            self.assertEqual(fixture.ledger.read_bytes(), before)

    def test_check_rejects_unknown_secret_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an otherwise valid ledger was extended with a raw secret field.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            receipt["secret_token"] = "raw-secret-value"
            fixture.ledger.write_text(json.dumps(data), encoding="utf-8")

            # When: the receipt ledger is checked through its real CLI surface.
            completed = run_receipt(["check", str(fixture.ledger)])

            # Then: unknown fields are rejected rather than silently discarded.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unexpected receipt fields", completed.stderr)

    def test_check_rejects_idempotency_key_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an authorized receipt whose idempotency key was changed after approval.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            receipt["idempotency_key"] = "publish:test:tampered"
            fixture.ledger.write_text(json.dumps(data), encoding="utf-8")

            # When: the tampered ledger is checked.
            completed = run_receipt(["check", str(fixture.ledger)])

            # Then: the canonical approval binding detects the idempotency change.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("canonical action hash", completed.stderr)

    def test_check_rejects_action_id_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an authorized receipt whose action identifier was changed after approval.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            data = load_json_object(fixture.ledger)
            receipts = object_list_field(data, "receipts")
            receipt = receipts[0]
            receipt["action_id"] = "tampered-action"
            fixture.ledger.write_text(json.dumps(data), encoding="utf-8")

            # When: the tampered ledger is checked.
            completed = run_receipt(["check", str(fixture.ledger)])

            # Then: the canonical approval binding detects the identifier change.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("canonical action hash", completed.stderr)

    def test_terminal_state_rejects_time_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an action was dispatched at a known time.
            fixture = make_fixture(Path(tmp))
            self.assertEqual(authorize_fixture(fixture).returncode, 0)
            dispatched = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "dispatched", "--at", timestamp()]
            )
            self.assertEqual(dispatched.returncode, 0, dispatched.stderr)

            # When: completion is recorded with an earlier timestamp.
            completed = run_receipt(
                ["record", "--ledger", str(fixture.ledger), "--action-id", "action-1", "--status", "completed", "--at", timestamp(timedelta(minutes=-1))]
            )

            # Then: the impossible terminal chronology is rejected.
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("before dispatch", completed.stderr)


if __name__ == "__main__":
    unittest.main()
