#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from discord_contract_types import ControlContractError
from host_coordination import (
    CodexAuthState,
    HostObservation,
    HostStatus,
    HostStateStore,
    WriteLeaseRequest,
    WriteLeaseStore,
)


class HostCoordinationTests(unittest.TestCase):
    def test_heartbeat_records_capabilities_mapping_and_auth_observation_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a target Mac heartbeat without credentials or secret material.
            root = Path(tmp) / "sejong"
            observation = HostObservation(
                host_id="mac-studio",
                observed_at="2026-07-19T10:00:00Z",
                status=HostStatus.CONNECTED,
                codex_auth=CodexAuthState.OBSERVED_READY,
                capabilities=("codex-process", "git-worktree"),
                repo_paths=(("king-sejong", "/srv/king-sejong"),),
            )

            # When: Core persists the host observation.
            path = HostStateStore(root).record_heartbeat(observation)

            # Then: state is runtime-only and carries no credential value.
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(path.is_relative_to(root / "state" / "discord"))
            self.assertEqual(payload["hosts"][0]["codex_auth"], "observed_ready")
            self.assertEqual(payload["hosts"][0]["repo_paths"]["king-sejong"], "/srv/king-sejong")
            self.assertNotIn("token", path.read_text(encoding="utf-8").lower())

    def test_active_repo_write_lease_prevents_cross_host_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: one active write lease for a repository.
            root = Path(tmp) / "sejong"
            store = WriteLeaseStore(root)
            first = WriteLeaseRequest(
                lease_id="lease-1",
                ticket_id="ticket-1",
                host_id="mac-studio",
                repo_id="king-sejong",
                workspace=Path(tmp) / "worktree-1",
                acquired_at="2026-07-19T10:00:00Z",
                expires_at="2026-07-19T11:00:00Z",
                host_status=HostStatus.CONNECTED,
            )
            store.acquire(first)

            # When: another host attempts a concurrent write lease on that repo.
            with self.assertRaises(ControlContractError) as raised:
                store.acquire(WriteLeaseRequest(
                    lease_id="lease-2",
                    ticket_id="ticket-2",
                    host_id="macbook",
                    repo_id="king-sejong",
                    workspace=Path(tmp) / "worktree-2",
                    acquired_at="2026-07-19T10:05:00Z",
                    expires_at="2026-07-19T11:05:00Z",
                    host_status=HostStatus.CONNECTED,
                ))

            # Then: Core refuses the collision and makes no sandbox claim.
            self.assertEqual(raised.exception.code, "write_collision")
            payload = json.loads(store.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["leases"][0]["isolation_claim"], "edit_isolation_only")

    def test_stale_lease_requires_evidenced_recovery_before_reassignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: an apparently expired lease whose remote host state is unknown.
            root = Path(tmp) / "sejong"
            store = WriteLeaseStore(root)
            first = WriteLeaseRequest(
                "lease-old",
                "ticket-old",
                "mac-studio",
                "agent-company",
                Path(tmp) / "worktree-old",
                "2026-07-19T08:00:00Z",
                "2026-07-19T09:00:00Z",
                HostStatus.CONNECTED,
            )
            store.acquire(first)
            replacement = WriteLeaseRequest(
                "lease-new",
                "ticket-new",
                "macbook",
                "agent-company",
                Path(tmp) / "worktree-new",
                "2026-07-19T10:00:00Z",
                "2026-07-19T11:00:00Z",
                HostStatus.CONNECTED,
            )

            # When/Then: elapsed time alone cannot steal an unresolved lease.
            with self.assertRaises(ControlContractError) as raised:
                store.acquire(replacement, observed_at="2026-07-19T10:00:00Z")
            self.assertEqual(raised.exception.code, "lease_recovery_required")

            # When: an explicit matching recovery receipt releases the old lease.
            store.recover_release(
                "lease-old",
                "ticket-old",
                released_at="2026-07-19T10:01:00Z",
                evidence_ref="receipt://host-disconnect-audit",
            )

            # Then: a new host can acquire the now-uncontested repository.
            acquired = store.acquire(replacement, observed_at="2026-07-19T10:02:00Z")
            self.assertEqual(acquired["lease_id"], "lease-new")

    def test_disconnected_and_unknown_hosts_have_distinct_conservative_states(self) -> None:
        cases = (
            (HostStatus.DISCONNECTED, "host_disconnected"),
            (HostStatus.UNKNOWN, "host_state_unknown"),
        )
        for status, code in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                # Given: a write request from a host that is not currently connected.
                request = WriteLeaseRequest(
                    "lease-1",
                    "ticket-1",
                    "mac-studio",
                    "king-sejong",
                    Path(tmp) / "worktree",
                    "2026-07-19T10:00:00Z",
                    "2026-07-19T11:00:00Z",
                    status,
                )

                # When/Then: Core records the exact conservative refusal state.
                with self.assertRaises(ControlContractError) as raised:
                    WriteLeaseStore(Path(tmp) / "sejong").acquire(request)
                self.assertEqual(raised.exception.code, code)

    def test_write_lease_id_cannot_be_reused_for_another_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a lease identifier already bound to one repository and ticket.
            store = WriteLeaseStore(Path(tmp) / "sejong")
            first = WriteLeaseRequest(
                "lease-shared", "ticket-1", "mac-studio", "repo-1",
                Path(tmp) / "worktree-1", "2026-07-19T10:00:00Z",
                "2026-07-19T11:00:00Z", HostStatus.CONNECTED,
            )
            store.acquire(first)

            # When/Then: another repository cannot reuse that durable identity.
            with self.assertRaises(ControlContractError) as raised:
                store.acquire(WriteLeaseRequest(
                    "lease-shared", "ticket-2", "macbook", "repo-2",
                    Path(tmp) / "worktree-2", "2026-07-19T10:05:00Z",
                    "2026-07-19T11:05:00Z", HostStatus.CONNECTED,
                ))
            self.assertEqual(raised.exception.code, "duplicate_lease")


if __name__ == "__main__":
    unittest.main()
