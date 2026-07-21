#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
#   uv run docs/sejong/scripts/test_worker_resource_cleanup.py
# ──────────────────────────

from __future__ import annotations

import unittest
from dataclasses import replace
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from delegation_run_model import (
    Backend,
    Budget,
    DelegationContractError,
    DelegationRun,
    JsonObject,
    Worker,
    WorkerId,
    load_run,
    save_run,
)
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
LEASE_CLI = SCRIPT_PATH.with_name("worker_resource_lease.py")
NATIVE_ADAPTER = SCRIPT_PATH.with_name("native_delegation_adapter.py")


def run_lease(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LEASE_CLI), *arguments],
        text=True,
        capture_output=True,
    )


def create_released_lease(path: Path) -> None:
    created = run_lease(
        "create", str(path),
        "--lease-id", "lease-worker-a",
        "--run-id", "cleanup-run",
        "--wave-id", "wave-1",
        "--worker-id", "worker-a",
        "--backend", "native",
        "--backend-worker-ref", "codex-thread://thread-a",
        "--cleanup-capability", "host_owned_exact",
        "--resource-id", "runtime-worker-a",
        "--resource-kind", "host_runtime_group",
        "--identity-ref", "codex-thread://thread-a",
        "--ownership-source", "host_reported",
        "--cleanup-policy", "automatic",
    )
    if created.returncode != 0:
        raise AssertionError(created.stderr)
    releasing = run_lease("transition", str(path), "--status", "releasing")
    if releasing.returncode != 0:
        raise AssertionError(releasing.stderr)
    released = run_lease(
        "transition", str(path), "--status", "released",
        "--proof-ref", "host-cleanup://thread-a",
    )
    if released.returncode != 0:
        raise AssertionError(released.stderr)


def terminal_run() -> DelegationRun:
    run = DelegationRun(
        run_id="cleanup-run",
        created_at="2026-07-21T00:00:00Z",
        budget=Budget(1, 1, 1, 1),
        workers=(Worker(WorkerId("worker-a"), Backend.NATIVE, 0),),
    )
    run = add_wave(run, WaveId("wave-1"), (WorkerId("worker-a"),), ())
    run = open_wave(run, WaveId("wave-1"))
    return record_terminal(
        run,
        TerminalReceiptRequest(
            receipt_id=ReceiptId("terminal-worker-a"),
            wave_id=WaveId("wave-1"),
            worker_id=WorkerId("worker-a"),
            backend_worker_ref="codex-thread://thread-a",
            worker_contract_ref="contract://worker-a",
            worker_output_ref="output://worker-a",
            terminal_status=TerminalStatus.COMPLETED,
            summary="worker-a terminal",
            evidence_refs=("evidence://worker-a",),
            blocker=None,
        ),
    )


def cleanup_receipt(status: str, *, blocker: str | None) -> JsonObject:
    return {
        "format": "sejong.worker-cleanup-receipt/v0.1-draft",
        "receipt_type": "worker_cleanup",
        "receipt_id": "cleanup-worker-a",
        "run_id": "cleanup-run",
        "wave_id": "wave-1",
        "worker_id": "worker-a",
        "backend": "native",
        "backend_worker_ref": "codex-thread://thread-a",
        "resource_lease_ref": "lease://worker-a",
        "resource_lease_id": "lease-worker-a",
        "cleanup_capability": "host_owned_exact",
        "cleanup_status": status,
        "released_resource_ids": ["runtime-worker-a"] if status == "released" else [],
        "preserved_resource_ids": [],
        "failed_resource_ids": [] if status == "released" else ["runtime-worker-a"],
        "proof_refs": ["host-cleanup://thread-a"],
        "blocker": blocker,
        "authority": "cleanup_evidence_only",
        "created_at": "2026-07-21T00:01:00Z",
    }


class WorkerResourceCleanupBarrierTests(unittest.TestCase):
    def test_exact_host_runtime_lease_rejects_mismatched_identity(self) -> None:
        # Given: an exact host-owned lease names a different runtime identity than its worker.
        with tempfile.TemporaryDirectory() as tmp:
            lease_path = Path(tmp) / "lease.json"

            # When: Core parses the ownership request.
            result = run_lease(
                "create", str(lease_path),
                "--lease-id", "lease-worker-a",
                "--run-id", "cleanup-run",
                "--wave-id", "wave-1",
                "--worker-id", "worker-a",
                "--backend", "native",
                "--backend-worker-ref", "codex-thread://thread-a",
                "--cleanup-capability", "host_owned_exact",
                "--resource-id", "runtime-worker-a",
                "--resource-kind", "host_runtime_group",
                "--identity-ref", "codex-thread://different-thread",
                "--ownership-source", "host_reported",
                "--cleanup-policy", "automatic",
            )

            # Then: the lease is rejected before persistence.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("host runtime identity must match backend worker ref", result.stderr)
            self.assertFalse(lease_path.exists())

    def test_check_rejects_tampered_resource_status(self) -> None:
        # Given: a released lease whose resource state was changed back to active.
        with tempfile.TemporaryDirectory() as tmp:
            lease_path = Path(tmp) / "lease.json"
            create_released_lease(lease_path)
            payload = json.loads(lease_path.read_text(encoding="utf-8"))
            payload["resources"][0]["status"] = "active"
            lease_path.write_text(json.dumps(payload), encoding="utf-8")

            # When: the persisted lease is checked.
            result = run_lease("check", str(lease_path))

            # Then: state disagreement cannot become cleanup evidence.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resource status must match lease status", result.stderr)

    def test_check_rejects_non_string_blocker(self) -> None:
        # Given: a released lease whose nullable blocker was replaced by another JSON type.
        with tempfile.TemporaryDirectory() as tmp:
            lease_path = Path(tmp) / "lease.json"
            create_released_lease(lease_path)
            payload = json.loads(lease_path.read_text(encoding="utf-8"))
            payload["blocker"] = 42
            lease_path.write_text(json.dumps(payload), encoding="utf-8")

            # When: the persisted lease is checked.
            result = run_lease("check", str(lease_path))

            # Then: malformed blocker evidence is rejected instead of normalized to null.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("blocker must be a non-empty string or null", result.stderr)

    def test_fan_in_rejects_terminal_worker_without_cleanup_receipt(self) -> None:
        # Given/When/Then: terminal output alone cannot close a native worker wave.
        with self.assertRaisesRegex(DelegationContractError, "missing cleanup receipts"):
            fan_in(terminal_run(), WaveId("wave-1"))

    def test_native_adapter_records_cleanup_only_from_released_matching_lease(self) -> None:
        # Given: a terminal native worker and an exact released runtime lease.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            lease_path = Path(tmp) / "lease.json"
            save_run(run_path, terminal_run())
            create_released_lease(lease_path)

            # When: the host-native adapter projects cleanup evidence into the run.
            recorded = subprocess.run(
                [
                    sys.executable, str(NATIVE_ADAPTER), "record-cleanup", str(run_path),
                    "--receipt-id", "cleanup-worker-a",
                    "--agent-thread-id", "thread-a",
                    "--worker-resource-lease", str(lease_path),
                ],
                text=True,
                capture_output=True,
            )

            # Then: fan-in sees the correlated cleanup receipt and passes.
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            closed, receipt = fan_in(load_run(run_path), WaveId("wave-1"))
            self.assertEqual(receipt["aggregate_status"], "passed")
            self.assertEqual(closed.waves[0]["status"], "passed")

    def test_exact_host_runtime_lease_reaches_released_with_proof(self) -> None:
        # Given: Core owns a dedicated lease path for one native worker runtime.
        with tempfile.TemporaryDirectory() as tmp:
            lease_path = Path(tmp) / "lease.json"
            created = run_lease(
                "create",
                str(lease_path),
                "--lease-id", "lease-worker-a",
                "--run-id", "cleanup-run",
                "--wave-id", "wave-1",
                "--worker-id", "worker-a",
                "--backend", "native",
                "--backend-worker-ref", "codex-thread://thread-a",
                "--cleanup-capability", "host_owned_exact",
                "--resource-id", "runtime-worker-a",
                "--resource-kind", "host_runtime_group",
                "--identity-ref", "codex-thread://thread-a",
                "--ownership-source", "host_reported",
                "--cleanup-policy", "automatic",
            )
            self.assertEqual(created.returncode, 0, created.stderr)

            # When: host teardown starts and then supplies exact cleanup proof.
            releasing = run_lease("transition", str(lease_path), "--status", "releasing")
            released = run_lease(
                "transition",
                str(lease_path),
                "--status", "released",
                "--proof-ref", "host-cleanup://thread-a",
            )

            # Then: the durable lease records a released runtime and its proof.
            self.assertEqual(releasing.returncode, 0, releasing.stderr)
            self.assertEqual(released.returncode, 0, released.stderr)
            payload = json.loads(lease_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "released")
            self.assertEqual(payload["resources"][0]["status"], "released")
            self.assertEqual(payload["proof_refs"], ["host-cleanup://thread-a"])

    def test_released_cleanup_receipt_allows_passed_fan_in(self) -> None:
        # Given: the native worker terminal and exact host cleanup receipts are correlated.
        run = terminal_run()
        run = replace(run, receipts=(*run.receipts, cleanup_receipt("released", blocker=None)))

        # When: Core closes the wave.
        closed, receipt = fan_in(run, WaveId("wave-1"))

        # Then: cleanup evidence participates in the passed fan-in receipt.
        self.assertEqual(receipt["aggregate_status"], "passed")
        self.assertEqual(receipt["cleanup_receipt_ids"], ["cleanup-worker-a"])
        self.assertEqual(closed.waves[0]["status"], "passed")

    def test_failed_cleanup_receipt_blocks_fan_in_success(self) -> None:
        # Given: worker output completed, but its exact host cleanup failed.
        run = terminal_run()
        run = replace(
            run,
            receipts=(*run.receipts, cleanup_receipt("failed", blocker="host runtime remained active")),
        )

        # When: Core closes the wave.
        closed, receipt = fan_in(run, WaveId("wave-1"))

        # Then: the wave is blocked and cannot authorize another wave.
        self.assertEqual(receipt["aggregate_status"], "blocked")
        self.assertEqual(receipt["blocking_receipt_ids"], ["cleanup-worker-a"])
        self.assertEqual(closed.waves[0]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
