#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
#   uv run docs/sejong/scripts/test_delegation_wave_validation.py
# ──────────────────────────

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from delegation_run import check_failures
from delegation_run_model import Backend, Budget, DelegationContractError, DelegationRun, Worker, WorkerId, save_run
from delegation_wave import (
    ReceiptId,
    TerminalReceiptRequest,
    TerminalStatus,
    WaveId,
    add_wave,
    fan_in,
    open_wave,
    record_terminal,
)


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SEUNGJEONGWON = SCRIPT_PATH.with_name("seungjeongwon_run.py")
SCHEMA_PATH = SCRIPT_PATH.parents[1] / "delegation-run.schema.json"


def terminal_run(status: TerminalStatus = TerminalStatus.COMPLETED) -> DelegationRun:
    run = DelegationRun(
        run_id="correlation-run",
        created_at="2026-07-11T00:00:00Z",
        budget=Budget(1, 1, 1, 1),
        workers=(Worker(WorkerId("worker-a"), Backend.NATIVE, 0),),
    )
    run = add_wave(run, WaveId("wave-1"), (WorkerId("worker-a"),), ())
    run = open_wave(run, WaveId("wave-1"))
    run = record_terminal(
        run,
        TerminalReceiptRequest(
            receipt_id=ReceiptId("receipt-worker-a"),
            wave_id=WaveId("wave-1"),
            worker_id=WorkerId("worker-a"),
            backend_worker_ref="native://worker-a",
            worker_contract_ref="contract://worker-a",
            worker_output_ref="output://worker-a",
            terminal_status=status,
            summary="worker-a terminal",
            evidence_refs=("evidence://worker-a",),
            blocker=None if status is TerminalStatus.COMPLETED else f"{status.value} disposition",
        ),
    )
    return run


def closed_run(status: TerminalStatus = TerminalStatus.COMPLETED) -> DelegationRun:
    return fan_in(terminal_run(status), WaveId("wave-1"))[0]


def cleanup_receipt(
    run: DelegationRun,
    *,
    status: str = "released",
    receipt_id: str = "cleanup-worker-a",
) -> dict:
    terminal = next(item for item in run.receipts if item.get("receipt_type") == "worker_terminal")
    worker_ref = str(terminal["backend_worker_ref"])
    released = [worker_ref] if status == "released" else []
    preserved = [worker_ref] if status in {"preserved", "audit_only"} else []
    failed = [worker_ref] if status == "failed" else []
    return {
        "format": "sejong.worker-cleanup-receipt/v0.1-draft",
        "receipt_type": "worker_cleanup",
        "receipt_id": receipt_id,
        "run_id": run.run_id,
        "wave_id": "wave-1",
        "worker_id": "worker-a",
        "backend": "native",
        "backend_worker_ref": worker_ref,
        "resource_lease_ref": "lease://worker-a",
        "resource_lease_id": "lease-worker-a",
        "cleanup_capability": "host_owned_exact",
        "cleanup_status": status,
        "released_resource_ids": released,
        "preserved_resource_ids": preserved,
        "failed_resource_ids": failed,
        "proof_refs": [f"proof://worker-a/{status}"],
        "blocker": None if status == "released" else f"cleanup {status}",
        "authority": "cleanup_evidence_only",
        "created_at": "2026-07-11T00:01:00Z",
    }


def cleanup_run(status: str = "released") -> DelegationRun:
    run = terminal_run()
    run = replace(run, receipts=(*run.receipts, cleanup_receipt(run, status=status)))
    return fan_in(run, WaveId("wave-1"))[0]


def payload_for(run: DelegationRun, path: Path) -> dict:
    save_run(path, run)
    return json.loads(path.read_text(encoding="utf-8"))


def write_payload(path: Path, payload: dict) -> tuple[str, ...]:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return check_failures(path)


def run_seungjeongwon(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SEUNGJEONGWON), *arguments],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


class DelegationWaveCorrelationTests(unittest.TestCase):
    def test_optional_released_cleanup_is_linked_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            run = cleanup_run()
            payload = payload_for(run, path)
            fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
            cleanup = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_cleanup")

            self.assertEqual(check_failures(path), ())
            self.assertEqual(cleanup["authority"], "cleanup_evidence_only")
            self.assertEqual(fan_in_receipt["authority"], "orchestration_evidence_only")
            self.assertEqual(fan_in_receipt["cleanup_receipt_ids"], ["cleanup-worker-a"])
            self.assertEqual(fan_in_receipt["aggregate_status"], "passed")
            self.assertEqual(fan_in_receipt["blocking_receipt_ids"], [])
            self.assertEqual(
                next(item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal")["terminal_status"],
                "completed",
            )

    def test_cleanup_free_legacy_run_remains_valid_and_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(closed_run(), path)
            fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")

            self.assertEqual(check_failures(path), ())
            self.assertNotIn("cleanup_receipt_ids", fan_in_receipt)

    @unittest.skipIf(jsonschema is None, "jsonschema is required for schema-instance validation")
    def test_schema_accepts_optional_cleanup_and_rejects_malformed_state(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        valid_payloads = []
        for status in ("released", "preserved", "failed", "audit_only"):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(cleanup_run(status), path)
            jsonschema.validate(payload, schema)
            valid_payloads.append(payload)

        cases = (
            ("authority", "final_authority"),
            ("cleanup_status", "completed"),
            ("released_resource_ids", []),
            ("proof_refs", []),
            ("blocker", "unexpected blocker"),
        )
        for field, value in cases:
            with self.subTest(field=field):
                malformed = deepcopy(valid_payloads[0])
                cleanup = next(
                    item for item in malformed["receipts"] if item["receipt_type"] == "worker_cleanup"
                )
                cleanup[field] = value
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(malformed, schema)

    def test_cleanup_boundary_and_binding_tampering_is_rejected(self) -> None:
        cases = {
            "format": ("format", "wrong-format"),
            "authority": ("authority", "final_authority"),
            "run": ("run_id", "other-run"),
            "wave": ("wave_id", "unknown-wave"),
            "worker": ("worker_id", "unknown-worker"),
            "backend": ("backend", "team_executor"),
            "backend_ref": ("backend_worker_ref", "native://other-worker"),
            "lease_ref": ("resource_lease_ref", ""),
            "lease_id": ("resource_lease_id", ""),
            "capability": ("cleanup_capability", "process_manager"),
            "status": ("cleanup_status", "completed"),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(cleanup_run(), path)
                cleanup = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_cleanup")
                cleanup[field] = value
                self.assertTrue(write_payload(path, payload))

    def test_cleanup_status_resource_proof_and_blocker_rules_are_enforced(self) -> None:
        cases = (
            ("released", "released_resource_ids", []),
            ("released", "preserved_resource_ids", ["native://worker-a"]),
            ("released", "proof_refs", []),
            ("released", "blocker", "unexpected blocker"),
            ("preserved", "preserved_resource_ids", []),
            ("preserved", "blocker", None),
            ("failed", "failed_resource_ids", []),
            ("audit_only", "preserved_resource_ids", []),
        )
        for status, field, value in cases:
            with self.subTest(status=status, field=field), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(cleanup_run(status), path)
                cleanup = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_cleanup")
                cleanup[field] = value
                self.assertTrue(write_payload(path, payload))

    def test_duplicate_cleanup_and_resource_lease_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(cleanup_run(), path)
            cleanup = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_cleanup")
            duplicate = deepcopy(cleanup)
            duplicate["receipt_id"] = "cleanup-worker-a-duplicate"
            payload["receipts"].insert(-1, duplicate)
            fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
            fan_in_receipt["cleanup_receipt_ids"].append(duplicate["receipt_id"])

            failures = write_payload(path, payload)

            self.assertTrue(any("cleanup receipt" in failure for failure in failures))
            self.assertIn("cleanup resource lease ids must be unique", failures)
            self.assertIn("cleanup resource lease refs must be unique", failures)
            self.assertIn("cleanup resource ids must be unique across receipts", failures)

    def test_fan_in_cleanup_references_and_blockers_are_exact(self) -> None:
        cases = {
            "missing": None,
            "unknown": ["cleanup-unknown"],
            "duplicate": ["cleanup-worker-a", "cleanup-worker-a"],
        }
        for name, value in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(cleanup_run(), path)
                fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
                if value is None:
                    fan_in_receipt.pop("cleanup_receipt_ids")
                else:
                    fan_in_receipt["cleanup_receipt_ids"] = value
                self.assertTrue(write_payload(path, payload))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(cleanup_run("preserved"), path)
            fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
            fan_in_receipt["blocking_receipt_ids"] = []
            self.assertTrue(write_payload(path, payload))

    def test_cleanup_cannot_substitute_for_terminal_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(cleanup_run(), path)
            payload["receipts"] = [
                item for item in payload["receipts"] if item["receipt_type"] != "worker_terminal"
            ]
            fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
            fan_in_receipt["terminal_receipt_ids"] = []

            failures = write_payload(path, payload)

            self.assertTrue(failures)
            self.assertTrue(any("terminal" in failure for failure in failures))

    def test_released_cleanup_cannot_upgrade_nonpassed_terminal(self) -> None:
        expected = {
            TerminalStatus.FAILED: "failed",
            TerminalStatus.TIMED_OUT: "failed",
            TerminalStatus.BLOCKED: "blocked",
        }
        for terminal_status, aggregate_status in expected.items():
            with self.subTest(terminal_status=terminal_status), tempfile.TemporaryDirectory() as tmp:
                run = terminal_run(terminal_status)
                run = replace(run, receipts=(*run.receipts, cleanup_receipt(run)))
                run = fan_in(run, WaveId("wave-1"))[0]
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(run, path)
                fan_in_receipt = next(
                    item for item in payload["receipts"] if item["receipt_type"] == "fan_in"
                )
                terminal = next(
                    item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal"
                )

                self.assertEqual(check_failures(path), ())
                self.assertEqual(terminal["terminal_status"], terminal_status.value)
                self.assertEqual(fan_in_receipt["aggregate_status"], aggregate_status)
                self.assertEqual(fan_in_receipt["blocking_receipt_ids"], ["receipt-worker-a"])

    def test_nonreleased_cleanup_blocks_or_fails_without_rewriting_terminal_status(self) -> None:
        expected = {
            "preserved": "blocked",
            "audit_only": "blocked",
            "failed": "failed",
        }
        for cleanup_status, aggregate_status in expected.items():
            with self.subTest(cleanup_status=cleanup_status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(cleanup_run(cleanup_status), path)
                fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
                terminal = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal")

                self.assertEqual(check_failures(path), ())
                self.assertEqual(fan_in_receipt["aggregate_status"], aggregate_status)
                self.assertEqual(fan_in_receipt["blocking_receipt_ids"], ["cleanup-worker-a"])
                self.assertEqual(terminal["terminal_status"], "completed")

    def test_generated_terminal_aggregates_are_valid(self) -> None:
        # Given/When/Then: every aggregate generated by Core passes persisted validation.
        for status in (TerminalStatus.COMPLETED, TerminalStatus.FAILED, TerminalStatus.BLOCKED):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                save_run(path, closed_run(status))
                self.assertEqual(check_failures(path), ())

    def test_passed_fan_in_without_terminal_receipts_is_rejected(self) -> None:
        # Given: a passed fan-in whose terminal evidence was deleted.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(closed_run(), path)
            payload["receipts"] = [receipt for receipt in payload["receipts"] if receipt["receipt_type"] == "fan_in"]

            # When/Then: the persisted run is not accepted on fan-in claims alone.
            self.assertTrue(write_payload(path, payload))

    def test_terminal_identity_and_state_tampering_is_rejected(self) -> None:
        cases = {
            "receipt_id": ("receipt_id", "forged-receipt"),
            "worker_id": ("worker_id", "unknown-worker"),
            "terminal_status": ("terminal_status", "failed"),
            "run_id": ("run_id", "other-run"),
            "backend": ("backend", "team_executor"),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(closed_run(), path)
                terminal = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal")
                terminal[field] = value
                self.assertTrue(write_payload(path, payload))

    def test_fan_in_coverage_and_recomputed_fields_are_enforced(self) -> None:
        cases = {
            "required_workers": ("required_worker_ids", ["worker-a", "worker-extra"]),
            "terminal_ids": ("terminal_receipt_ids", ["receipt-worker-a", "receipt-worker-a"]),
            "aggregate": ("aggregate_status", "blocked"),
            "blocking_ids": ("blocking_receipt_ids", ["receipt-worker-a"]),
            "run_id": ("run_id", "other-run"),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(closed_run(), path)
                fan_in_receipt = next(item for item in payload["receipts"] if item["receipt_type"] == "fan_in")
                fan_in_receipt[field] = value
                self.assertTrue(write_payload(path, payload))

    def test_orphan_receipts_and_open_wave_fan_in_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delegation-run.json"
            payload = payload_for(closed_run(), path)
            orphan = dict(next(item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal"))
            orphan.update(receipt_id="orphan-receipt", wave_id="unknown-wave")
            payload["receipts"].append(orphan)
            self.assertTrue(write_payload(path, payload))

        for status in ("pending", "active"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(closed_run(), path)
                payload["waves"][0]["status"] = status
                self.assertTrue(write_payload(path, payload))

    def test_receipt_boundary_and_required_references_are_enforced(self) -> None:
        cases = {
            "format": ("format", "wrong-format"),
            "authority": ("authority", "final_authority"),
            "backend_worker_ref": ("backend_worker_ref", ""),
            "worker_contract_ref": ("worker_contract_ref", ""),
            "worker_output_ref": ("worker_output_ref", ""),
            "evidence_refs": ("evidence_refs", []),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "delegation-run.json"
                payload = payload_for(closed_run(), path)
                terminal = next(item for item in payload["receipts"] if item["receipt_type"] == "worker_terminal")
                terminal[field] = value
                self.assertTrue(write_payload(path, payload))

    def test_seungjeongwon_rejects_detached_and_later_tampered_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            delegation_path = root / "delegation-run.json"
            fan_in_path = root / "fan-in.json"
            seungjeongwon_path = root / "seungjeongwon-run.json"
            run = closed_run()
            save_run(delegation_path, run)
            fan_in_receipt = next(item for item in run.receipts if item["receipt_type"] == "fan_in")
            fan_in_path.write_text(json.dumps(fan_in_receipt), encoding="utf-8")
            started = run_seungjeongwon(
                [
                    "start", "--path", str(seungjeongwon_path), "--run-id", "seung-correlation",
                    "--goal", "Reject tampered delegation evidence.",
                    "--success-criterion", "Only correlated fan-in is accepted.",
                    "--verification-method", "Run persisted validation.",
                ]
            )
            self.assertEqual(started.returncode, 0, started.stderr)

            payload = payload_for(run, delegation_path)
            payload["receipts"] = [item for item in payload["receipts"] if item["receipt_type"] == "fan_in"]
            delegation_path.write_text(json.dumps(payload), encoding="utf-8")
            detached = run_seungjeongwon(
                [
                    "add-fan-in", "--path", str(seungjeongwon_path),
                    "--delegation-run", str(delegation_path), "--receipt", str(fan_in_path),
                ]
            )
            self.assertNotEqual(detached.returncode, 0)
            self.assertIn("invalid delegation run ref", detached.stderr)

            save_run(delegation_path, run)
            attached = run_seungjeongwon(
                [
                    "add-fan-in", "--path", str(seungjeongwon_path),
                    "--delegation-run", str(delegation_path), "--receipt", str(fan_in_path),
                ]
            )
            self.assertEqual(attached.returncode, 0, attached.stderr)
            payload = payload_for(run, delegation_path)
            payload["receipts"][0]["run_id"] = "tampered-run"
            delegation_path.write_text(json.dumps(payload), encoding="utf-8")
            embedded = run_seungjeongwon(["check", "--path", str(seungjeongwon_path)])
            self.assertNotEqual(embedded.returncode, 0)
            self.assertIn("invalid delegation run ref", embedded.stderr)

    def test_tampered_passed_dependency_cannot_open_downstream_wave(self) -> None:
        run = closed_run()
        extra_worker = Worker(WorkerId("worker-b"), Backend.NATIVE, 0)
        run = replace(
            run,
            budget=Budget(2, 1, 1, 2),
            workers=(*run.workers, extra_worker),
        )
        run = add_wave(
            run,
            WaveId("wave-2"),
            (WorkerId("worker-b"),),
            (WaveId("wave-1"),),
        )
        tampered = replace(
            run,
            receipts=tuple(
                receipt for receipt in run.receipts
                if receipt.get("receipt_type") != "worker_terminal"
            ),
        )

        with self.assertRaisesRegex(DelegationContractError, "invalid persisted wave state"):
            open_wave(tampered, WaveId("wave-2"))


if __name__ == "__main__":
    unittest.main()
