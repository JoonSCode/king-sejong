#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
ADAPTER = SCRIPT_PATH.with_name("native_delegation_adapter.py")
DELEGATION_RUN = SCRIPT_PATH.with_name("delegation_run.py")


def run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        text=True,
        capture_output=True,
    )


def prepare_wave(path: Path, *, backend: str = "native") -> None:
    commands = (
        (
            "init",
            str(path),
            "--run-id",
            "native-adapter-test",
            "--max-total-workers",
            "1",
            "--max-concurrency",
            "1",
            "--max-spawn-depth",
            "1",
            "--max-rounds",
            "1",
        ),
        (
            "register-worker",
            str(path),
            "--worker-id",
            "worker-a",
            "--backend",
            backend,
            "--spawn-depth",
            "0",
        ),
        ("add-wave", str(path), "--wave-id", "wave-1", "--worker-id", "worker-a"),
        ("open-wave", str(path), "--wave-id", "wave-1"),
    )
    for command in commands:
        result = run_script(DELEGATION_RUN, *command)
        if result.returncode != 0:
            raise AssertionError(result.stderr)


def record_native(
    path: Path, *, thread_id: str = "thread-123", blocker: str | None = None
) -> subprocess.CompletedProcess[str]:
    arguments = [
        ADAPTER,
        "record-terminal",
        str(path),
        "--receipt-id",
        "receipt-worker-a",
        "--wave-id",
        "wave-1",
        "--worker-id",
        "worker-a",
        "--agent-thread-id",
        thread_id,
        "--worker-contract-ref",
        "contract://worker-a",
        "--worker-output-ref",
        "output://worker-a",
        "--status",
        "completed",
        "--summary",
        "native worker completed",
        "--evidence-ref",
        "evidence://worker-a",
    ]
    if blocker is not None:
        arguments.extend(("--blocker", blocker))
    return run_script(*arguments)


class NativeDelegationAdapterTests(unittest.TestCase):
    def test_native_terminal_receipt_passes_existing_fan_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            fan_in_path = Path(tmp) / "fan-in.json"
            prepare_wave(run_path)

            recorded = record_native(run_path)
            joined = run_script(
                DELEGATION_RUN,
                "fan-in",
                str(run_path),
                "--wave-id",
                "wave-1",
                "--output",
                str(fan_in_path),
            )

            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertEqual(joined.returncode, 0, joined.stderr)
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            terminal = next(
                item
                for item in payload["receipts"]
                if item["receipt_type"] == "worker_terminal"
            )
            self.assertEqual(terminal["backend"], "native")
            self.assertEqual(
                terminal["backend_worker_ref"], "codex-thread://thread-123"
            )
            self.assertEqual(
                json.loads(fan_in_path.read_text(encoding="utf-8"))["aggregate_status"],
                "passed",
            )

    def test_rejects_team_executor_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            prepare_wave(run_path, backend="team_executor")

            result = record_native(run_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("worker backend must be native", result.stderr)

    def test_rejects_empty_native_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "delegation-run.json"
            prepare_wave(run_path)

            result = record_native(run_path, thread_id="")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent_thread_id must be a non-empty string", result.stderr)

    def test_rejects_completed_receipt_with_blocker(self) -> None:
        for blocker in ("worker reported blocked", ""):
            with self.subTest(blocker=blocker), tempfile.TemporaryDirectory() as tmp:
                run_path = Path(tmp) / "delegation-run.json"
                prepare_wave(run_path)

                result = record_native(run_path, blocker=blocker)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("completed receipt cannot carry blocker", result.stderr)


if __name__ == "__main__":
    unittest.main()
