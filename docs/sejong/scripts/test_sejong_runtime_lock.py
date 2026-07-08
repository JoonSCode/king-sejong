#!/usr/bin/env python3
# noqa: SIZE_OK -- runtime lock race tests stay colocated with the lock contract
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
sys.path.insert(0, str(SEJONG_ROOT))

import scripts.sejong_runtime_lock as sejong_runtime_lock  # noqa: E402
from scripts.sejong_runtime_lock import (  # noqa: E402
    InvalidRuntimeLockName,
    InvalidRuntimeLockRetryIntervalSeconds,
    InvalidRuntimeLockStaleAfterSeconds,
    InvalidRuntimeLockTimeout,
    RuntimeLockClass,
    RuntimeLockRequest,
    RuntimeLockTimeout,
    acquire_runtime_lock,
)


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class CoordinatedStaleReasonTimeout(Exception):
    session_id: str

    def __str__(self) -> str:
        return f"timed out waiting for stale contenders: {self.session_id}"


def read_json(path: Path) -> dict[str, JsonValue]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def request_for(sejong_home: Path, lock_name: str, session_id: str) -> RuntimeLockRequest:
    return RuntimeLockRequest(
        sejong_home=sejong_home,
        lock_name=lock_name,
        lock_class=RuntimeLockClass.ACTIVE_POINTER,
        owner_session_id=session_id,
        owner_device_id="device-a",
        operation="test lock operation",
        timeout_seconds=0.05,
        stale_after_seconds=60.0,
        retry_interval_seconds=0.005,
    )


class SejongRuntimeLockTests(unittest.TestCase):
    def test_exclusive_acquisition_when_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: one session owns a runtime lock.
            sejong_home = Path(tmp)
            first = acquire_runtime_lock(request_for(sejong_home, "active-pointer", "session-a"))

            # When: another session attempts the same lock.
            with self.assertRaises(RuntimeLockTimeout) as raised:
                acquire_runtime_lock(request_for(sejong_home, "active-pointer", "session-b"))

            # Then: the second session sees owner metadata and the first lock remains.
            lock_path = sejong_home / "state" / "locks" / "active-pointer.lock"
            record = read_json(lock_path)
            self.assertEqual(record["owner_session_id"], "session-a")
            self.assertEqual(raised.exception.owner_session_id, "session-a")
            first.release()

    def test_invalid_timeout_values_are_rejected_at_direct_helper_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: direct helper requests carry invalid timeout values.
            sejong_home = Path(tmp)

            # When / Then: each invalid timeout fails before filesystem acquisition.
            for index, timeout_seconds in enumerate([float("nan"), float("inf"), float("-inf"), 0.0, -0.01]):
                with self.subTest(timeout_seconds=timeout_seconds):
                    request = RuntimeLockRequest(
                        sejong_home=sejong_home,
                        lock_name=f"invalid-timeout-{index}",
                        lock_class=RuntimeLockClass.ACTIVE_POINTER,
                        owner_session_id="session-a",
                        owner_device_id="device-a",
                        operation="invalid timeout direct helper",
                        timeout_seconds=timeout_seconds,
                    )
                    with self.assertRaises(InvalidRuntimeLockTimeout):
                        acquire_runtime_lock(request)

    def test_invalid_stale_after_values_are_rejected_at_direct_helper_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: direct helper requests carry invalid stale thresholds.
            sejong_home = Path(tmp)

            # When / Then: each invalid stale threshold fails before filesystem acquisition.
            for index, stale_after_seconds in enumerate([float("nan"), float("inf"), float("-inf"), 0.0, -0.01]):
                with self.subTest(stale_after_seconds=stale_after_seconds):
                    request = RuntimeLockRequest(
                        sejong_home=sejong_home,
                        lock_name=f"invalid-stale-after-{index}",
                        lock_class=RuntimeLockClass.ACTIVE_POINTER,
                        owner_session_id="session-a",
                        owner_device_id="device-a",
                        operation="invalid stale threshold direct helper",
                        stale_after_seconds=stale_after_seconds,
                    )
                    with self.assertRaises(InvalidRuntimeLockStaleAfterSeconds):
                        acquire_runtime_lock(request)

    def test_invalid_stale_after_values_cannot_replace_live_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: session-a owns a live runtime lock.
            sejong_home = Path(tmp)
            first = acquire_runtime_lock(request_for(sejong_home, "held-invalid-stale", "session-a"))
            lock_path = sejong_home / "state" / "locks" / "held-invalid-stale.lock"

            try:
                # When / Then: invalid stale thresholds fail fast and preserve the live owner.
                for stale_after_seconds in [0.0, -0.01, float("nan"), float("inf")]:
                    with self.subTest(stale_after_seconds=stale_after_seconds):
                        request = RuntimeLockRequest(
                            sejong_home=sejong_home,
                            lock_name="held-invalid-stale",
                            lock_class=RuntimeLockClass.ACTIVE_POINTER,
                            owner_session_id="session-b",
                            owner_device_id="device-a",
                            operation="invalid stale threshold held lock",
                            timeout_seconds=0.05,
                            stale_after_seconds=stale_after_seconds,
                            retry_interval_seconds=0.005,
                        )
                        with self.assertRaises(InvalidRuntimeLockStaleAfterSeconds):
                            acquire_runtime_lock(request)
                        self.assertEqual(read_json(lock_path)["owner_session_id"], "session-a")
            finally:
                first.release()

    def test_invalid_retry_interval_values_are_rejected_at_direct_helper_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: direct helper requests carry invalid retry intervals.
            sejong_home = Path(tmp)

            # When / Then: each invalid retry interval fails before acquisition retry logic.
            for index, retry_interval_seconds in enumerate([float("nan"), float("inf"), float("-inf"), 0.0, -0.01]):
                with self.subTest(retry_interval_seconds=retry_interval_seconds):
                    request = RuntimeLockRequest(
                        sejong_home=sejong_home,
                        lock_name=f"invalid-retry-interval-{index}",
                        lock_class=RuntimeLockClass.ACTIVE_POINTER,
                        owner_session_id="session-a",
                        owner_device_id="device-a",
                        operation="invalid retry interval direct helper",
                        retry_interval_seconds=retry_interval_seconds,
                    )
                    with self.assertRaises(InvalidRuntimeLockRetryIntervalSeconds):
                        acquire_runtime_lock(request)

    def test_invalid_retry_interval_values_fail_fast_when_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: session-a owns a live runtime lock.
            sejong_home = Path(tmp)
            first = acquire_runtime_lock(request_for(sejong_home, "held-invalid-retry", "session-a"))
            lock_path = sejong_home / "state" / "locks" / "held-invalid-retry.lock"

            try:
                # When / Then: invalid retry intervals fail fast and never escape from time.sleep.
                for retry_interval_seconds in [float("nan"), float("inf"), float("-inf"), 0.0, -0.01]:
                    with self.subTest(retry_interval_seconds=retry_interval_seconds):
                        request = RuntimeLockRequest(
                            sejong_home=sejong_home,
                            lock_name="held-invalid-retry",
                            lock_class=RuntimeLockClass.ACTIVE_POINTER,
                            owner_session_id="session-b",
                            owner_device_id="device-a",
                            operation="invalid retry interval held lock",
                            timeout_seconds=0.05,
                            retry_interval_seconds=retry_interval_seconds,
                        )
                        with self.assertRaises(InvalidRuntimeLockRetryIntervalSeconds):
                            acquire_runtime_lock(request)
                        self.assertEqual(read_json(lock_path)["owner_session_id"], "session-a")
            finally:
                first.release()

    def test_nan_timeout_fails_fast_when_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: another session already holds the runtime lock.
            sejong_home = Path(tmp)
            first = acquire_runtime_lock(request_for(sejong_home, "held-nan", "session-a"))
            script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(SEJONG_ROOT / "scripts")!r})
from sejong_runtime_lock import RuntimeLockClass, RuntimeLockRequest, acquire_runtime_lock

acquire_runtime_lock(
    RuntimeLockRequest(
        sejong_home=Path({str(sejong_home)!r}),
        lock_name="held-nan",
        lock_class=RuntimeLockClass.ACTIVE_POINTER,
        owner_session_id="session-b",
        owner_device_id="device-a",
        operation="invalid nan held lock",
        timeout_seconds=float("nan"),
        retry_interval_seconds=0.005,
    )
)
"""

            # When: a direct helper call uses a nan timeout against the held lock.
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", script],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=0.5,
                )
            finally:
                first.release()
            elapsed = time.monotonic() - started

            # Then: the child exits quickly with a clear invalid-timeout exception.
            self.assertLess(elapsed, 0.5)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("invalid runtime lock timeout", completed.stderr)

    def test_stale_lock_is_replaced_when_owner_is_gone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a stale lock record from a gone process.
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "run-context.lock"
            write_json(
                lock_path,
                {
                    "format": "sejong.runtime-lock/v0.1-draft",
                    "lock_name": "run-context",
                    "lock_class": "run-context",
                    "owner_session_id": "stale-session",
                    "owner_run_id": "run-a",
                    "owner_repo_id": "repo-a",
                    "owner_device_id": "device-a",
                    "owner_process_id": 999999,
                    "operation": "stale operation",
                    "token": "old-token",
                    "created_at": "2000-01-01T00:00:00Z",
                    "heartbeat_at": "2000-01-01T00:00:00Z",
                    "stale_after_seconds": 1.0,
                },
            )

            # When: a new session acquires the same lock.
            request = RuntimeLockRequest(
                sejong_home=sejong_home,
                lock_name="run-context",
                lock_class=RuntimeLockClass.RUN_CONTEXT,
                owner_session_id="fresh-session",
                owner_device_id="device-a",
                operation="replace stale runtime lock",
                timeout_seconds=0.05,
                stale_after_seconds=1.0,
                retry_interval_seconds=0.005,
            )
            acquired = acquire_runtime_lock(request)

            # Then: the new lock owns the file and records the stale break.
            record = read_json(lock_path)
            self.assertEqual(record["owner_session_id"], "fresh-session")
            self.assertEqual(record["stale_previous_owner_session_id"], "stale-session")
            acquired.release()

    def test_old_owner_release_after_stale_replacement_preserves_replacement_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an old owner reads its stale token before a replacement is written.
            sejong_home = Path(tmp)
            old_lock = acquire_runtime_lock(request_for(sejong_home, "run-context", "session-a"))
            lock_path = sejong_home / "state" / "locks" / "run-context.lock"
            replacement_record: JsonObject = {
                "format": "sejong.runtime-lock/v0.1-draft",
                "lock_name": "run-context",
                "lock_class": "run-context",
                "owner_session_id": "session-b",
                "owner_run_id": "run-b",
                "repo_id": "repo-a",
                "owner_device_id": "device-a",
                "owner_process_id": os.getpid(),
                "operation": "replacement lock",
                "token": "replacement-token",
                "created_at": "2026-07-01T00:00:00Z",
                "heartbeat_at": "2026-07-01T00:00:00Z",
                "stale_after_seconds": 1.0,
            }
            original_read_lock_record = sejong_runtime_lock.read_lock_record
            replacement_written = False

            def replacing_read(path: Path) -> JsonObject | None:
                nonlocal replacement_written
                record = original_read_lock_record(path)
                if path == lock_path and not replacement_written:
                    write_json(lock_path, replacement_record)
                    replacement_written = True
                return record

            # When: the old owner releases after the replacement is already in place.
            sejong_runtime_lock.read_lock_record = replacing_read
            try:
                with self.assertRaises(sejong_runtime_lock.RuntimeLockReleaseError):
                    old_lock.release()
            finally:
                sejong_runtime_lock.read_lock_record = original_read_lock_record

            # Then: the replacement lock remains owned by the replacement owner.
            replaced_record = read_json(lock_path)
            self.assertEqual(replaced_record["owner_session_id"], "session-b")

    def test_timeout_when_active_lock_does_not_become_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an active lock is already held.
            sejong_home = Path(tmp)
            first = acquire_runtime_lock(request_for(sejong_home, "artifact-ref", "session-a"))

            # When: a second acquisition uses a bounded timeout.
            started = time.monotonic()
            with self.assertRaises(RuntimeLockTimeout):
                acquire_runtime_lock(request_for(sejong_home, "artifact-ref", "session-b"))
            elapsed = time.monotonic() - started

            # Then: the attempt fails promptly instead of hanging.
            self.assertLess(elapsed, 0.25)
            first.release()

    def test_release_removes_only_owned_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a session acquired a cleanup lock.
            sejong_home = Path(tmp)
            lock = acquire_runtime_lock(request_for(sejong_home, "cleanup", "session-a"))
            lock_path = sejong_home / "state" / "locks" / "cleanup.lock"

            # When: the owner releases it.
            lock.release()

            # Then: the lock file is removed and a new owner can acquire it.
            self.assertFalse(lock_path.exists())
            second = acquire_runtime_lock(request_for(sejong_home, "cleanup", "session-b"))
            second.release()

    def test_invalid_lock_name_is_rejected_at_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a path-like lock name crosses the helper boundary.
            sejong_home = Path(tmp)
            request = request_for(sejong_home, "../active-pointer", "session-a")

            # When / Then: the malformed name is rejected before filesystem access.
            with self.assertRaises(InvalidRuntimeLockName):
                acquire_runtime_lock(request)

    def test_malformed_stale_metadata_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a malformed lock file older than the stale threshold.
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "malformed.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("{not-json", encoding="utf-8")
            old_time = time.time() - 10.0
            os.utime(lock_path, (old_time, old_time))

            # When: a session acquires that lock with a short stale threshold.
            request = request_for(sejong_home, "malformed", "session-a")
            request = RuntimeLockRequest(
                sejong_home=request.sejong_home,
                lock_name=request.lock_name,
                lock_class=request.lock_class,
                owner_session_id=request.owner_session_id,
                owner_device_id=request.owner_device_id,
                operation=request.operation,
                timeout_seconds=request.timeout_seconds,
                stale_after_seconds=1.0,
            )
            acquired = acquire_runtime_lock(request)

            # Then: the malformed stale file is replaced by structured metadata.
            record = read_json(lock_path)
            self.assertEqual(record["owner_session_id"], "session-a")
            self.assertEqual(record["stale_break_reason"], "malformed lock metadata")
            acquired.release()

    def test_only_one_contender_acquires_when_stale_break_races(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: two contenders observe the same stale lock before either can replace it.
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "race.lock"
            write_json(
                lock_path,
                {
                    "format": "sejong.runtime-lock/v0.1-draft",
                    "lock_name": "race",
                    "lock_class": "run-context",
                    "owner_session_id": "stale-session",
                    "owner_run_id": "run-a",
                    "repo_id": "repo-a",
                    "owner_device_id": "device-a",
                    "owner_process_id": 999999,
                    "operation": "stale operation",
                    "token": "old-token",
                    "created_at": "2000-01-01T00:00:00Z",
                    "heartbeat_at": "2000-01-01T00:00:00Z",
                    "stale_after_seconds": 1.0,
                },
            )
            observed_lock = threading.Lock()
            observed_sessions: set[str] = set()
            both_observed_stale = threading.Event()
            acquired_sessions: list[str] = []
            timeout_sessions: list[str] = []
            worker_errors: list[str] = []
            original_stale_reason: Callable[[JsonObject | None, Path, float], str | None] = (
                sejong_runtime_lock.stale_lock_reason
            )

            def coordinated_stale_reason(
                record: JsonObject | None,
                path: Path,
                stale_after_seconds: float,
            ) -> str | None:
                reason = original_stale_reason(record, path, stale_after_seconds)
                thread_name = threading.current_thread().name
                if reason is not None and thread_name in {"session-a", "session-b"}:
                    with observed_lock:
                        observed_sessions.add(thread_name)
                        if len(observed_sessions) == 2:
                            both_observed_stale.set()
                    if not both_observed_stale.wait(timeout=0.25):
                        raise CoordinatedStaleReasonTimeout(thread_name)
                return reason

            def attempt(session_id: str) -> None:
                request = RuntimeLockRequest(
                    sejong_home=sejong_home,
                    lock_name="race",
                    lock_class=RuntimeLockClass.RUN_CONTEXT,
                    owner_session_id=session_id,
                    owner_device_id="device-a",
                    operation="race stale lock replacement",
                    timeout_seconds=0.05,
                    stale_after_seconds=1.0,
                    retry_interval_seconds=0.005,
                )
                try:
                    acquired = acquire_runtime_lock(request)
                except RuntimeLockTimeout:
                    timeout_sessions.append(session_id)
                    return
                except (threading.BrokenBarrierError, RuntimeError) as exc:
                    worker_errors.append(f"{session_id}: {exc}")
                    return
                acquired_sessions.append(acquired.owner_session_id)

            sejong_runtime_lock.stale_lock_reason = coordinated_stale_reason
            try:
                # When: both sessions race to acquire by breaking that stale lock.
                session_a = threading.Thread(target=attempt, args=("session-a",), name="session-a")
                session_b = threading.Thread(target=attempt, args=("session-b",), name="session-b")
                session_a.start()
                session_b.start()
                session_a.join(timeout=5.0)
                session_b.join(timeout=5.0)
            finally:
                sejong_runtime_lock.stale_lock_reason = original_stale_reason

            # Then: the stale record is broken once; the other contender times out.
            self.assertEqual(worker_errors, [])
            self.assertFalse(session_a.is_alive())
            self.assertFalse(session_b.is_alive())
            self.assertEqual(len(acquired_sessions), 1, acquired_sessions)
            self.assertEqual(len(timeout_sessions), 1, timeout_sessions)


if __name__ == "__main__":
    unittest.main()
