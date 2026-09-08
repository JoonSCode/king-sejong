#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
CONTEXT_SCRIPT = SEJONG_ROOT / "scripts" / "sejong_context.py"
HOOK_SCRIPT = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
sys.path.insert(0, str(CONTEXT_SCRIPT.parent))
import sejong_context as context_module  # noqa: E402


def run_context(
    args: list[str],
    *,
    sejong_home: Path,
    lock_timeout_seconds: str = "0.05",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTEXT_SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "SEJONG_HOME": str(sejong_home),
            "SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS": lock_timeout_seconds,
        },
    )


def start_context(sejong_home: Path, run_id: str, *extra: str, session_id: str = "session-test") -> Path:
    result = run_context(
        [
            "start",
            "--repo-root",
            str(REPO_ROOT),
            "--run-id",
            run_id,
            "--session-id",
            session_id,
            *extra,
        ],
        sejong_home=sejong_home,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    line = next(item for item in result.stdout.splitlines() if item.startswith("run_context="))
    return Path(line.removeprefix("run_context="))


def run_pre_tool_hook(context_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), "PreToolUse", "--context", str(context_path)],
        input=json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch\n"
                },
                "cwd": str(REPO_ROOT),
            }
        ),
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout) if result.stdout.strip() else {}


class SejongContextTests(unittest.TestCase):
    def test_start_update_doctor_and_close_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            run_path = start_context(
                sejong_home,
                "ctx-test",
                "--current-surface",
                "jiphyeonjeon",
                "--required-route",
                "jiphyeonjeon",
                "--required-route",
                "uigwe",
                "--required-route",
                "seungjeongwon",
                "--protected-path",
                "docs/sejong/",
                "--last-user-intent",
                "test durable context",
            )
            self.assertFalse((sejong_home / "state" / "active-context.json").exists())
            context = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(context["context_revision"], 1)
            self.assertEqual(context["context_status"], "active")
            self.assertEqual(len(context["repo_identities"]), 1)

            update = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "seungjeongwon",
                    "--append-route",
                    "uigwe",
                    "--append-route",
                    "seungjeongwon",
                    "--add-pending-gate",
                    "verification",
                    "--add-evidence-ref",
                    "evidence.json",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(update.returncode, 0, update.stderr)
            updated = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["context_revision"], 2)
            self.assertEqual(updated["current_surface"], "seungjeongwon")
            self.assertEqual(updated["route_sequence"], ["jiphyeonjeon", "uigwe", "seungjeongwon"])
            self.assertEqual(updated["evidence_refs"], ["evidence.json"])

            doctor = run_context(
                ["doctor", "--session-id", "session-test", "--repo-root", str(REPO_ROOT)],
                sejong_home=sejong_home,
            )
            self.assertEqual(doctor.returncode, 0, doctor.stderr)

            close = run_context(
                ["close", "--session-id", "session-test", "--expect-revision", "1"],
                sejong_home=sejong_home,
            )
            self.assertEqual(close.returncode, 0, close.stderr)
            closed = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(closed["context_status"], "closed")
            bindings = list((sejong_home / "state" / "session-bindings").glob("*.json"))
            self.assertEqual(json.loads(bindings[0].read_text(encoding="utf-8"))["state"], "unbound")

    def test_start_research_or_advice_terminal_has_no_execution_or_planning_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = start_context(
                Path(tmp),
                "advice-terminal",
                "--current-surface",
                "jiphyeonjeon",
            )
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], [])
            self.assertEqual(context["pending_gates"], [])

    def test_start_settled_goal_bearing_requires_only_seungjeongwon_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = start_context(Path(tmp), "goal-bearing", "--goal-bearing")
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_start_unresolved_material_planning_requires_uigwe_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = start_context(
                Path(tmp),
                "planning-boundary",
                "--goal-bearing",
                "--required-route",
                "uigwe",
            )
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(
                context["pending_gates"],
                ["uigwe_promotion_required", "seungjeongwon_receipt_required"],
            )

    def test_start_explicit_uigwe_entry_has_no_unsatisfied_promotion_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = start_context(
                Path(tmp),
                "explicit-uigwe",
                "--current-surface",
                "uigwe",
                "--goal-bearing",
                "--required-route",
                "uigwe",
            )
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["route_sequence"], ["uigwe"])
            self.assertEqual(context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_legacy_active_pointer_lock_does_not_control_new_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            lock_path = sejong_home / "state" / "locks" / "active-pointer.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text('{"legacy":true}', encoding="utf-8")
            result = run_context(
                ["start", "--repo-root", str(REPO_ROOT), "--run-id", "legacy-lock", "--session-id", "session-new"],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(lock_path.read_text(encoding="utf-8"), '{"legacy":true}')

    def test_start_rejects_invalid_lock_timeout_env_without_traceback(self) -> None:
        for invalid_timeout in ("not-a-number", "nan", "inf", "-1", "0"):
            with self.subTest(invalid_timeout=invalid_timeout), tempfile.TemporaryDirectory() as tmp:
                result = run_context(
                    ["start", "--repo-root", str(REPO_ROOT), "--run-id", "invalid-timeout"],
                    sejong_home=Path(tmp),
                    lock_timeout_seconds=invalid_timeout,
                )
                combined = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, combined)
                self.assertIn("expected a finite positive number of seconds", combined)
                self.assertNotIn("Traceback", combined)

    def test_start_records_objective_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = start_context(
                Path(tmp),
                "objective-context",
                "--objective-id",
                "review-board",
                "--objective-ref",
                "artifacts/review-board.md",
            )
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["objective_id"], "review-board")
            self.assertEqual(context["objective_refs"], ["artifacts/review-board.md"])

    def test_update_can_require_seungjeongwon_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "receipt-update")
            result = run_context(
                ["update", "--session-id", "session-test", "--require-seungjeongwon-receipt"],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("seungjeongwon", context["required_route_sequence"])
            self.assertIn("seungjeongwon_receipt_required", context["pending_gates"])

    def test_route_only_seungjeongwon_does_not_imply_execution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            start_path = start_context(
                sejong_home,
                "route-only-start",
                "--required-route",
                "seungjeongwon",
                session_id="route-only-start-session",
            )
            started = json.loads(start_path.read_text(encoding="utf-8"))
            self.assertEqual(started["required_route_sequence"], ["seungjeongwon"])
            self.assertEqual(started["pending_gates"], [])

            update_path = start_context(
                sejong_home,
                "route-only-update",
                session_id="route-only-update-session",
            )
            result = run_context(
                [
                    "update",
                    "--session-id",
                    "route-only-update-session",
                    "--add-required-route",
                    "seungjeongwon",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = json.loads(update_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["required_route_sequence"], ["seungjeongwon"])
            self.assertEqual(updated["pending_gates"], [])

    def test_update_required_uigwe_route_adds_promotion_gate_until_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "planning-update")
            result = run_context(
                ["update", "--session-id", "session-test", "--add-required-route", "uigwe"],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["uigwe"])
            self.assertEqual(context["pending_gates"], ["uigwe_promotion_required"])

    def test_update_explicitly_resolves_unentered_uigwe_boundary_without_dropping_execution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(
                sejong_home,
                "resolved-planning-boundary",
                "--goal-bearing",
                "--required-route",
                "uigwe",
            )
            result = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--clear-pending-gate",
                    "uigwe_promotion_required",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_update_entering_uigwe_satisfies_promotion_gate_and_keeps_required_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(
                sejong_home,
                "entered-planning-boundary",
                "--goal-bearing",
                "--required-route",
                "uigwe",
            )
            result = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "uigwe",
                    "--append-route",
                    "uigwe",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_redundant_uigwe_gate_clear_after_entry_keeps_required_route_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(
                sejong_home,
                "entered-boundary-redundant-clear",
                "--goal-bearing",
                "--required-route",
                "uigwe",
            )
            entered = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "uigwe",
                    "--append-route",
                    "uigwe",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(entered.returncode, 0, entered.stderr)
            redundant_clear = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--clear-pending-gate",
                    "uigwe_promotion_required",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(redundant_clear.returncode, 0, redundant_clear.stderr)
            context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(context["pending_gates"], ["seungjeongwon_receipt_required"])

    def test_reopened_uigwe_boundary_survives_unrelated_update_and_blocks_until_current_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "reopened-planning-boundary", "--goal-bearing")
            completed_prior_route = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "seungjeongwon",
                    "--set-route-sequence",
                    "sejong",
                    "--set-route-sequence",
                    "uigwe",
                    "--set-route-sequence",
                    "seungjeongwon",
                    "--clear-pending-gate",
                    "seungjeongwon_receipt_required",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(completed_prior_route.returncode, 0, completed_prior_route.stderr)

            reopened = run_context(
                ["update", "--session-id", "session-test", "--add-required-route", "uigwe"],
                sejong_home=sejong_home,
            )
            self.assertEqual(reopened.returncode, 0, reopened.stderr)
            reopened_context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(reopened_context["required_route_sequence"], ["uigwe", "seungjeongwon"])
            self.assertEqual(reopened_context["pending_gates"], ["uigwe_promotion_required"])

            unrelated = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "jangyeongsil",
                    "--set-route-sequence",
                    "sejong",
                    "--set-route-sequence",
                    "uigwe",
                    "--set-route-sequence",
                    "seungjeongwon",
                    "--set-route-sequence",
                    "jangyeongsil",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(unrelated.returncode, 0, unrelated.stderr)
            unrelated_context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(unrelated_context["pending_gates"], ["uigwe_promotion_required"])
            blocked = run_pre_tool_hook(path)
            self.assertEqual(blocked["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn(
                "Uigwe planning boundary is pending",
                blocked["hookSpecificOutput"]["permissionDecisionReason"],
            )

            entered = run_context(
                [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    "uigwe",
                    "--append-route",
                    "uigwe",
                ],
                sejong_home=sejong_home,
            )
            self.assertEqual(entered.returncode, 0, entered.stderr)
            entered_context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(entered_context["pending_gates"], [])
            self.assertNotEqual(
                run_pre_tool_hook(path).get("hookSpecificOutput", {}).get("permissionDecision"),
                "deny",
            )

    def test_settled_goal_upgrade_inserts_uigwe_before_unentered_executor_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(
                sejong_home,
                "settled-to-uigwe-upgrade",
                "--goal-bearing",
                "--required-route",
                "jiphyeonjeon",
                "--protected-path",
                "README.md",
            )
            upgraded = run_context(
                ["update", "--session-id", "session-test", "--add-required-route", "uigwe"],
                sejong_home=sejong_home,
            )
            self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
            upgraded_context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                upgraded_context["required_route_sequence"],
                ["jiphyeonjeon", "uigwe", "seungjeongwon"],
            )
            self.assertEqual(
                upgraded_context["pending_gates"],
                ["uigwe_promotion_required", "seungjeongwon_receipt_required"],
            )

            for surface in ("jiphyeonjeon", "uigwe", "seungjeongwon"):
                args = [
                    "update",
                    "--session-id",
                    "session-test",
                    "--current-surface",
                    surface,
                    "--append-route",
                    surface,
                ]
                if surface == "seungjeongwon":
                    args.extend(["--clear-pending-gate", "seungjeongwon_receipt_required"])
                routed = run_context(args, sejong_home=sejong_home)
                self.assertEqual(routed.returncode, 0, routed.stderr)

            executed_context = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                executed_context["route_sequence"],
                ["sejong", "jiphyeonjeon", "uigwe", "seungjeongwon"],
            )
            self.assertEqual(executed_context["pending_gates"], [])
            self.assertNotEqual(
                run_pre_tool_hook(path).get("hookSpecificOutput", {}).get("permissionDecision"),
                "deny",
            )

    def test_context_revision_cas_rejects_stale_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "context-cas")
            first = run_context(
                ["update", "--context", str(path), "--expect-context-revision", "1", "--last-user-intent", "first"],
                sejong_home=sejong_home,
            )
            stale = run_context(
                ["update", "--context", str(path), "--expect-context-revision", "1", "--last-user-intent", "stale"],
                sejong_home=sejong_home,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("context revision conflict", stale.stdout + stale.stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["last_user_intent"], "first")

    def test_save_context_rejects_missing_expected_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "context-cas-required")
            context = json.loads(path.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ValueError, "expected_context_revision is required"):
                context_module.save_context(context, sejong_home=sejong_home)

            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["context_revision"], 1)

    def test_save_context_rejects_immutable_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "context-immutable-identity")
            context = json.loads(path.read_text(encoding="utf-8"))
            context["active_context_id"] = "ctx-replacement-must-not-commit"

            with self.assertRaisesRegex(Exception, "context identity conflict"):
                context_module.save_context(
                    context,
                    expected_context_revision=1,
                    sejong_home=sejong_home,
                    operation="immutable identity regression",
                )

            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotEqual(persisted["active_context_id"], "ctx-replacement-must-not-commit")
            self.assertEqual(persisted["context_revision"], 1)

    def test_two_process_context_cas_allows_exactly_one_writer(self) -> None:
        # Given: two independent processes hold the same observed Context revision.
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "context-process-race")
            environment = {
                **os.environ,
                "SEJONG_HOME": str(sejong_home),
                "SEJONG_CONTEXT_LOCK_TIMEOUT_SECONDS": "2.0",
            }
            commands = [
                [
                    sys.executable,
                    str(CONTEXT_SCRIPT),
                    "update",
                    "--context",
                    str(path),
                    "--expect-context-revision",
                    "1",
                    "--last-user-intent",
                    intent,
                ]
                for intent in ("process-writer-a", "process-writer-b")
            ]

            # When: both processes race through the stable per-Context sidecar lock.
            processes = [
                subprocess.Popen(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(REPO_ROOT),
                    env=environment,
                )
                for command in commands
            ]
            results = [process.communicate(timeout=10) for process in processes]
            returncodes = [process.returncode for process in processes]
            context = json.loads(path.read_text(encoding="utf-8"))

        # Then: one commit advances revision once and the stale contender receives CAS conflict.
        self.assertEqual(sorted(returncodes), [0, 1])
        failed_output = "".join(
            stdout + stderr
            for process, (stdout, stderr) in zip(processes, results, strict=True)
            if process.returncode != 0
        )
        self.assertIn("context revision conflict", failed_output)
        self.assertEqual(context["context_revision"], 2)
        self.assertIn(context["last_user_intent"], {"process-writer-a", "process-writer-b"})

    def test_context_commit_survives_reconstructable_repo_index_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            path = start_context(sejong_home, "context-index-failure")
            repo_index_root = sejong_home / "state" / "repo-index"
            for index_path in repo_index_root.glob("*"):
                index_path.unlink()
            repo_index_root.rmdir()
            repo_index_root.write_text("not-a-directory", encoding="utf-8")

            updated = run_context(
                [
                    "update",
                    "--context",
                    str(path),
                    "--expect-context-revision",
                    "1",
                    "--last-user-intent",
                    "committed despite derived index failure",
                ],
                sejong_home=sejong_home,
            )
            context = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn("repo index update failed after the Context commit", updated.stderr)
        self.assertEqual(context["context_revision"], 2)
        self.assertEqual(context["last_user_intent"], "committed despite derived index failure")

    def test_doctor_and_repair_require_explicit_non_authoritative_legacy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sejong_home = Path(tmp)
            fixture = json.loads(
                (SEJONG_ROOT / "examples" / "king-sejong-context.example.json").read_text(encoding="utf-8")
            )
            fixture["evidence_refs"] = [{"ref": "approved-direction"}]
            path = sejong_home / "state" / "active-context.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(fixture), encoding="utf-8")

            implicit = run_context(["doctor"], sejong_home=sejong_home)
            self.assertNotEqual(implicit.returncode, 0)
            self.assertIn("legacy active pointer is non-authoritative", implicit.stderr)

            doctor = run_context(["doctor", "--context", str(path)], sejong_home=sejong_home)
            self.assertNotEqual(doctor.returncode, 0)
            self.assertIn("evidence_refs must contain only non-empty strings", doctor.stderr)
            repair = run_context(["repair", "--context", str(path)], sejong_home=sejong_home)
            self.assertEqual(repair.returncode, 0, repair.stderr)
            run_path = sejong_home / "runs" / fixture["repo_id"] / fixture["run_id"] / "king-sejong-context.json"
            repaired = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["evidence_refs"], ["approved-direction"])


if __name__ == "__main__":
    unittest.main()
