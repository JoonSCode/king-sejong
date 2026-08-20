#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeAlias


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "sejong_doctor.py"
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def write_json(path: Path, payload: dict[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_doctor(args: list[str], sejong_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "SEJONG_HOME": str(sejong_home)},
    )


def context_payload(context_id: str, repo_root: Path, run_id: str) -> dict[str, JsonValue]:
    return {
        "format": "king-sejong.context/v0.1-draft",
        "active_context_id": context_id,
        "repo_id": "king-sejong-doctor-test",
        "repo_root": str(repo_root),
        "run_id": run_id,
        "session_id": f"session-{run_id}",
        "route_id": f"route-{run_id}",
        "current_surface": "seungjeongwon",
        "route_sequence": ["sejong", "seungjeongwon"],
        "required_route_sequence": ["seungjeongwon"],
        "last_user_intent": "doctor multisession test",
        "pending_gates": ["seungjeongwon_receipt_required"],
        "protected_paths": ["docs/sejong/"],
        "allowed_direct_change_types": ["typo"],
        "evidence_refs": [],
        "artifact_refs": [],
        "team_run_refs": [],
        "subagent_refs": [],
        "exit_conditions": ["user_explicitly_exits_sejong"],
        "last_updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def checks_by_name(payload: dict[str, JsonValue]) -> dict[str, dict[str, JsonValue]]:
    checks = payload["checks"]
    if not isinstance(checks, list):
        raise AssertionError("doctor payload checks must be a list")
    return {str(check["name"]): check for check in checks if isinstance(check, dict)}


class SejongDoctorTests(unittest.TestCase):
    def test_doctor_reports_managed_paths_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_doctor(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "--skip-python-deps",
                    "--skip-active-context",
                    "--json",
                ],
                Path(tmp),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.doctor-result/v0.1-draft")
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual(checks["source-managed-paths"]["status"], "ok")
        self.assertEqual(checks["plugin-adapter-json"]["status"], "ok")

    def test_doctor_does_not_execute_installer_from_untrusted_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp) / "sejong-home"
            fake_repo = Path(tmp) / "fake-repo"
            marker = Path(tmp) / "executed-marker"
            installer = fake_repo / "scripts" / "install-sejong.sh"
            installer.parent.mkdir(parents=True)
            installer.write_text(f"#!/usr/bin/env bash\ntouch {marker}\nexit 0\n", encoding="utf-8")
            installer.chmod(0o755)

            result = run_doctor(
                [
                    "--repo-root",
                    str(fake_repo),
                    "--skip-python-deps",
                    "--skip-active-context",
                    "--json",
                ],
                sejong_home,
            )

        payload = json.loads(result.stdout)
        checks = checks_by_name(payload)
        self.assertFalse(marker.exists())
        self.assertEqual(checks["install-update-drift"]["status"], "warn")
        self.assertIn("trusted King Sejong source tree", str(checks["install-update-drift"]["detail"]))

    def test_doctor_does_not_execute_git_fsmonitor_from_untrusted_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp) / "sejong-home"
            fake_repo = Path(tmp) / "fake-repo"
            marker = Path(tmp) / "fsmonitor-marker"
            fsmonitor = Path(tmp) / "fsmonitor-hook.sh"
            fake_repo.mkdir()
            fsmonitor.write_text(f"#!/usr/bin/env bash\ntouch {marker}\nexit 0\n", encoding="utf-8")
            fsmonitor.chmod(0o755)
            subprocess.run(["git", "init", str(fake_repo)], text=True, capture_output=True, check=True)
            subprocess.run(
                ["git", "-C", str(fake_repo), "config", "core.fsmonitor", str(fsmonitor)],
                text=True,
                capture_output=True,
                check=True,
            )

            result = run_doctor(
                [
                    "--repo-root",
                    str(fake_repo),
                    "--skip-python-deps",
                    "--skip-active-context",
                    "--json",
                ],
                sejong_home,
            )

        payload = json.loads(result.stdout)
        checks = checks_by_name(payload)
        self.assertFalse(marker.exists())
        self.assertEqual(checks["git-status"]["status"], "warn")
        self.assertIn("trusted King Sejong source tree", str(checks["git-status"]["detail"]))

    def test_doctor_separates_durable_active_runs_from_exact_cleanup_binding_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            active_context = context_payload("ctx-active-run", REPO_ROOT, "active-run")
            write_json(sejong_home / "state" / "active-context.json", active_context)
            write_json(
                sejong_home / "runs" / "king-sejong-doctor-test" / "active-run" / "king-sejong-context.json",
                active_context,
            )

            result = run_doctor(["--repo-root", str(REPO_ROOT), "--skip-python-deps", "--json"], sejong_home)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        checks = checks_by_name(payload)
        self.assertEqual(checks["multisession-active-runs"]["status"], "warn")
        self.assertIn("active-run", str(checks["multisession-active-runs"]["detail"]))
        self.assertEqual(checks["runtime-cleanup-dry-run"]["status"], "ok")
        self.assertIn("no exactly bound active runs", str(checks["runtime-cleanup-dry-run"]["detail"]))

    def test_doctor_reports_non_authoritative_legacy_pointer_and_broken_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            stale_context = context_payload("ctx-stale", REPO_ROOT / "sibling", "stale-run")
            current_context = context_payload("ctx-current", REPO_ROOT, "current-run")
            current_context["artifact_refs"] = ["missing-seungjeongwon-run.json"]
            write_json(sejong_home / "state" / "active-context.json", stale_context)
            write_json(
                sejong_home / "runs" / "king-sejong-doctor-test" / "current-run" / "king-sejong-context.json",
                current_context,
            )

            result = run_doctor(["--repo-root", str(REPO_ROOT), "--skip-python-deps", "--json"], sejong_home)

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        checks = checks_by_name(payload)
        self.assertEqual(checks["active-pointer-staleness"]["status"], "warn")
        self.assertIn("ctx-stale", str(checks["active-pointer-staleness"]["detail"]))
        self.assertIn(
            "automatic_injection_authority=false",
            str(checks["active-pointer-staleness"]["detail"]),
        )
        self.assertEqual(checks["runtime-broken-refs"]["status"], "fail")
        self.assertIn("missing-seungjeongwon-run.json", str(checks["runtime-broken-refs"]["detail"]))

    def test_doctor_reports_stuck_lock_owner_metadata_without_repairing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
            lock_path = sejong_home / "state" / "locks" / "active-pointer.lock"
            write_json(
                lock_path,
                {
                    "format": "sejong.runtime-lock/v0.1-draft",
                    "lock_name": "active-pointer",
                    "lock_class": "active-pointer",
                    "owner_session_id": "session-owner",
                    "owner_run_id": "run-owner",
                    "owner_device_id": "device-owner",
                    "owner_process_id": 999999999,
                    "operation": "publish active context",
                    "created_at": stale_time,
                    "heartbeat_at": stale_time,
                    "stale_after_seconds": 1,
                },
            )

            result = run_doctor(["--repo-root", str(REPO_ROOT), "--skip-python-deps", "--skip-active-context", "--json"], sejong_home)

            lock_still_exists = lock_path.exists()

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        lock_check = checks_by_name(payload)["runtime-locks"]
        self.assertEqual(lock_check["status"], "warn")
        self.assertIn("session-owner", str(lock_check["detail"]))
        self.assertIn("run-owner", str(lock_check["detail"]))
        self.assertIn("device-owner", str(lock_check["detail"]))
        self.assertTrue(lock_still_exists)


if __name__ == "__main__":
    unittest.main()
