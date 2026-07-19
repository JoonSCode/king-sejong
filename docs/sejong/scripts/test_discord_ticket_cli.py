#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from discord_ticket_cli import DryRunRequest, run_dry_ticket
from test_discord_control_contract import valid_event, valid_policy


class DiscordTicketCliTests(unittest.TestCase):
    def test_local_dry_run_uses_contracts_without_live_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: isolated event, policy, target, workspace, and SEJONG_HOME paths.
            root = Path(tmp)
            event_path = root / "event.json"
            policy_path = root / "policy.json"
            targets_path = root / "targets.json"
            event_path.write_text(json.dumps(valid_event()), encoding="utf-8")
            policy_path.write_text(json.dumps(valid_policy()), encoding="utf-8")
            targets_path.write_text(json.dumps({
                "format": "sejong.discord-target-registry/v0.1-draft",
                "hosts": [{
                    "host_id": "mac-studio",
                    "enabled": True,
                    "codex_binary": "/usr/bin/false",
                    "repositories": [{"repo_id": "king-sejong", "repo_root": str(root / "repo")}],
                }],
            }), encoding="utf-8")

            # When: the local contract entry point handles the dry-run ticket.
            output = run_dry_ticket(DryRunRequest(
                event_path,
                policy_path,
                targets_path,
                root / "worktree",
                root / "sejong",
            ))

            # Then: it produces a receipt plan and explicitly reports no process invocation.
            self.assertEqual(output["status"], "dry_run")
            self.assertFalse(output["process_invoked"])
            self.assertTrue(Path(output["receipt_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
