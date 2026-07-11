#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run docs/sejong/scripts/test_delegation_run.py
# 3. Or make executable and run:
#      chmod +x docs/sejong/scripts/test_delegation_run.py && ./docs/sejong/scripts/test_delegation_run.py
# ─────────────────

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from delegation_run import launch_workers
from delegation_run_model import DelegationContractError, WorkerId


SCRIPT_PATH = Path(__file__).resolve()
DELEGATION_RUN = SCRIPT_PATH.with_name("delegation_run.py")
SCHEMA_PATH = SCRIPT_PATH.parents[1] / "delegation-run.schema.json"


def run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DELEGATION_RUN), *arguments],
        text=True,
        capture_output=True,
    )


def init_run(path: Path, *, total: int = 2, concurrency: int = 1, depth: int = 1, rounds: int = 1) -> subprocess.CompletedProcess[str]:
    return run_cli(
        [
            "init",
            str(path),
            "--run-id",
            "budget-test",
            "--max-total-workers",
            str(total),
            "--max-concurrency",
            str(concurrency),
            "--max-spawn-depth",
            str(depth),
            "--max-rounds",
            str(rounds),
        ]
    )


def register(path: Path, worker_id: str, *, depth: int = 0, backend: str = "native") -> subprocess.CompletedProcess[str]:
    return run_cli(
        [
            "register-worker",
            str(path),
            "--worker-id",
            worker_id,
            "--backend",
            backend,
            "--spawn-depth",
            str(depth),
        ]
    )


def add_wave(
    path: Path,
    wave_id: str,
    *worker_ids: str,
    depends_on: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    arguments = ["add-wave", str(path), "--wave-id", wave_id]
    for worker_id in worker_ids:
        arguments.extend(["--worker-id", worker_id])
    for dependency in depends_on:
        arguments.extend(["--depends-on", dependency])
    return run_cli(arguments)


def record_terminal(
    path: Path,
    worker_id: str,
    *,
    wave_id: str,
    status: str = "completed",
    blocker: str | None = None,
    receipt_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = [
        "record-terminal",
        str(path),
        "--receipt-id",
        receipt_id or f"receipt-{worker_id}",
        "--wave-id",
        wave_id,
        "--worker-id",
        worker_id,
        "--backend-worker-ref",
        f"host://{worker_id}",
        "--worker-contract-ref",
        f"contract://{worker_id}",
        "--worker-output-ref",
        f"output://{worker_id}",
        "--status",
        status,
        "--summary",
        f"{worker_id} terminal",
        "--evidence-ref",
        f"evidence://{worker_id}",
    ]
    if blocker is not None:
        arguments.extend(["--blocker", blocker])
    return run_cli(arguments)


class DelegationRunBudgetTests(unittest.TestCase):
    def test_init_persists_versioned_budget_and_empty_fanin_surfaces(self) -> None:
        # Given: a caller-provided bounded delegation run path.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"

            # When: the caller initializes the run.
            result = init_run(run_path, total=3, concurrency=2, depth=2, rounds=4)

            # Then: the persisted contract carries every budget and stable extension surface.
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "sejong.delegation-run/v0.1-draft")
            self.assertEqual(
                payload["budget"],
                {
                    "max_concurrency": 2,
                    "max_rounds": 4,
                    "max_spawn_depth": 2,
                    "max_total_workers": 3,
                },
            )
            self.assertEqual(payload["workers"], [])
            self.assertEqual(payload["waves"], [])
            self.assertEqual(payload["receipts"], [])

    def test_init_rejects_concurrency_above_total_workers(self) -> None:
        # Given: a budget whose concurrency is larger than its total-worker cap.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"

            # When: the caller initializes the run.
            result = init_run(run_path, total=1, concurrency=2)

            # Then: the invalid cross-field budget is rejected before persistence.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_concurrency cannot exceed max_total_workers", result.stderr)
            self.assertFalse(run_path.exists())

    def test_register_worker_rejects_total_worker_overflow(self) -> None:
        # Given: a delegation run whose only worker slot is occupied.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, total=1).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)

            # When: another native worker is registered.
            result = register(run_path, "worker-b")

            # Then: total-worker overflow is rejected without appending the worker.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_total_workers exceeded", result.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual([worker["worker_id"] for worker in payload["workers"]], ["worker-a"])

    def test_register_worker_rejects_spawn_depth_overflow(self) -> None:
        # Given: a delegation run with maximum spawn depth one.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, depth=1).returncode, 0)

            # When: a nested native worker at depth two is registered.
            result = register(run_path, "worker-deep", depth=2)

            # Then: the depth overflow is rejected.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_spawn_depth exceeded", result.stderr)

    def test_launch_workers_rejects_concurrency_overflow(self) -> None:
        # Given: two registered workers and one concurrent slot.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, concurrency=1).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(register(run_path, "worker-b").returncode, 0)

            # When: both workers are reserved for launch in one batch.
            result = run_cli(
                ["launch-workers", str(run_path), "--worker-id", "worker-a", "--worker-id", "worker-b"]
            )

            # Then: concurrency overflow is rejected without changing either status.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_concurrency exceeded", result.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual([worker["status"] for worker in payload["workers"]], ["registered", "registered"])

    def test_terminal_worker_releases_concurrency_slot(self) -> None:
        # Given: one launched worker has consumed the only concurrent slot.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, concurrency=1).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(register(run_path, "worker-b").returncode, 0)
            self.assertEqual(run_cli(["launch-workers", str(run_path), "--worker-id", "worker-a"]).returncode, 0)
            self.assertEqual(
                run_cli(
                    ["finish-worker", str(run_path), "--worker-id", "worker-a", "--status", "completed"]
                ).returncode,
                0,
            )

            # When: the second worker is launched.
            result = run_cli(["launch-workers", str(run_path), "--worker-id", "worker-b"])

            # Then: the released slot can be reserved again.
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_start_round_rejects_round_budget_overflow(self) -> None:
        # Given: a delegation run whose only round has started.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, rounds=1).returncode, 0)
            self.assertEqual(run_cli(["start-round", str(run_path), "--round-id", "round-1"]).returncode, 0)

            # When: a second round is started.
            result = run_cli(["start-round", str(run_path), "--round-id", "round-2"])

            # Then: max-round overflow is rejected.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("max_rounds exceeded", result.stderr)

    def test_check_rejects_unknown_budget_reference(self) -> None:
        # Given: a valid native worker whose budget reference is corrupted.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "native-worker").returncode, 0)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            payload["workers"][0]["budget_ref"] = "wrong.json#/budget"
            run_path.write_text(json.dumps(payload), encoding="utf-8")

            # When: the persisted run is checked.
            result = run_cli(["check", str(run_path)])

            # Then: the worker must carry the canonical run budget reference.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("worker budget_ref does not match run budget", result.stderr)

    def test_register_worker_rejects_negative_spawn_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)

            result = register(run_path, "worker-negative", depth=-1)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("spawn_depth must be non-negative", result.stderr)

    def test_finish_worker_rejects_worker_that_never_launched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)

            result = run_cli(
                ["finish-worker", str(run_path), "--worker-id", "worker-a", "--status", "completed"]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("worker is not launched", result.stderr)


class DelegationWaveReceiptTests(unittest.TestCase):
    def test_fan_in_output_failure_can_retry_without_mutating_closed_run(self) -> None:
        # Given: Core can close a wave, but the requested receipt destination cannot be published.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = root / "delegation-run.json"
            invalid_parent = root / "not-a-directory"
            invalid_parent.write_text("blocked", encoding="utf-8")
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
            self.assertEqual(record_terminal(run_path, "worker-a", wave_id="wave-1").returncode, 0)

            # When: publication fails after the embedded receipt is persisted, then a valid output is retried.
            failed = run_cli(
                ["fan-in", str(run_path), "--wave-id", "wave-1", "--output", str(invalid_parent / "fan-in.json")]
            )
            self.assertNotEqual(failed.returncode, 0)
            closed_run = run_path.read_bytes()
            output = root / "fan-in.json"
            retried = run_cli(["fan-in", str(run_path), "--wave-id", "wave-1", "--output", str(output)])

            # Then: retry republishes the exact receipt without changing the Core run.
            self.assertEqual(retried.returncode, 0, retried.stderr)
            self.assertEqual(run_path.read_bytes(), closed_run)
            run = json.loads(closed_run)
            embedded = next(receipt for receipt in run["receipts"] if receipt["receipt_type"] == "fan_in")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), embedded)

    def test_fan_in_retry_rejects_mismatched_existing_output(self) -> None:
        # Given: a closed wave and an output path containing a different receipt.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = root / "delegation-run.json"
            output = root / "fan-in.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
            self.assertEqual(record_terminal(run_path, "worker-a", wave_id="wave-1").returncode, 0)
            self.assertEqual(
                run_cli(["fan-in", str(run_path), "--wave-id", "wave-1", "--output", str(output)]).returncode,
                0,
            )
            output.write_text('{"receipt_id": "different"}\n', encoding="utf-8")
            closed_run = run_path.read_bytes()

            # When: the caller retries publication to the mismatched path.
            retried = run_cli(["fan-in", str(run_path), "--wave-id", "wave-1", "--output", str(output)])

            # Then: Core rejects the mismatch and preserves both artifacts.
            self.assertNotEqual(retried.returncode, 0)
            self.assertIn("does not match embedded fan-in receipt", retried.stderr)
            self.assertEqual(run_path.read_bytes(), closed_run)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"receipt_id": "different"})

    def test_launch_workers_cli_rejects_worker_assigned_to_declared_wave(self) -> None:
        # Given: a registered worker assigned to a pending dependency wave.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            before = run_path.read_bytes()

            # When: the caller tries to bypass open-wave through direct launch.
            result = run_cli(["launch-workers", str(run_path), "--worker-id", "worker-a"])

            # Then: Core rejects the bypass without mutating the run.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("assigned to a wave", result.stderr)
            self.assertEqual(run_path.read_bytes(), before)

    def test_launch_workers_api_rejects_worker_assigned_to_declared_wave(self) -> None:
        # Given: a registered worker assigned to a pending dependency wave.
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            before = run_path.read_bytes()

            # When/Then: the Python API enforces the same open-wave-only boundary.
            with self.assertRaisesRegex(DelegationContractError, "assigned to a wave"):
                launch_workers(run_path, (WorkerId("worker-a"),))
            self.assertEqual(run_path.read_bytes(), before)

    def test_downstream_wave_waits_for_passed_fan_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            fan_in_path = Path(tmp) / "wave-1-fan-in.json"
            self.assertEqual(init_run(run_path, total=2, concurrency=1, rounds=2).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(register(run_path, "worker-b").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-2", "worker-b", depends_on=("wave-1",)).returncode, 0)

            blocked = run_cli(["open-wave", str(run_path), "--wave-id", "wave-2"])
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("dependency fan-in has not passed", blocked.stderr)

            self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
            self.assertEqual(record_terminal(run_path, "worker-a", wave_id="wave-1").returncode, 0)
            joined = run_cli(
                ["fan-in", str(run_path), "--wave-id", "wave-1", "--output", str(fan_in_path)]
            )
            self.assertEqual(joined.returncode, 0, joined.stderr)
            self.assertEqual(json.loads(fan_in_path.read_text(encoding="utf-8"))["aggregate_status"], "passed")

            opened = run_cli(["open-wave", str(run_path), "--wave-id", "wave-2"])
            self.assertEqual(opened.returncode, 0, opened.stderr)

    def test_fan_in_rejects_missing_receipt_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path, total=2, concurrency=2).returncode, 0)
            self.assertEqual(register(run_path, "native-a").returncode, 0)
            self.assertEqual(register(run_path, "team-b", backend="team_executor").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "native-a", "team-b").returncode, 0)
            self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
            self.assertEqual(record_terminal(run_path, "native-a", wave_id="wave-1").returncode, 0)
            before = run_path.read_bytes()

            result = run_cli(["fan-in", str(run_path), "--wave-id", "wave-1"])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing terminal receipts", result.stderr)
            self.assertEqual(run_path.read_bytes(), before)

    def test_blocked_or_timed_out_receipt_never_becomes_success(self) -> None:
        cases = (("blocked", "blocked"), ("timed_out", "failed"))
        for terminal_status, aggregate_status in cases:
            with self.subTest(terminal_status=terminal_status), tempfile.TemporaryDirectory() as tmp:
                run_path = Path(tmp) / "delegation-run.json"
                self.assertEqual(init_run(run_path).returncode, 0)
                self.assertEqual(register(run_path, "worker-a").returncode, 0)
                self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
                self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
                self.assertEqual(
                    record_terminal(
                        run_path,
                        "worker-a",
                        wave_id="wave-1",
                        status=terminal_status,
                        blocker=f"{terminal_status} disposition",
                    ).returncode,
                    0,
                )

                result = run_cli(["fan-in", str(run_path), "--wave-id", "wave-1"])

                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(run_path.read_text(encoding="utf-8"))
                fan_in = [receipt for receipt in payload["receipts"] if receipt["receipt_type"] == "fan_in"][0]
                self.assertEqual(fan_in["aggregate_status"], aggregate_status)
                self.assertNotEqual(fan_in["aggregate_status"], "passed")

    def test_duplicate_terminal_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            self.assertEqual(init_run(run_path).returncode, 0)
            self.assertEqual(register(run_path, "worker-a").returncode, 0)
            self.assertEqual(add_wave(run_path, "wave-1", "worker-a").returncode, 0)
            self.assertEqual(run_cli(["open-wave", str(run_path), "--wave-id", "wave-1"]).returncode, 0)
            self.assertEqual(record_terminal(run_path, "worker-a", wave_id="wave-1").returncode, 0)

            duplicate = record_terminal(run_path, "worker-a", wave_id="wave-1", receipt_id="receipt-worker-a-2")

            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("terminal receipt already exists", duplicate.stderr)

if __name__ == "__main__":
    unittest.main()
