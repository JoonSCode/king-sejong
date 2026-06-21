#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "repo_context_candidate.py"


class RepoContextCandidateTests(unittest.TestCase):
    def test_candidate_is_read_only_and_rejects_transient_lessons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--repo-root",
                    str(repo_root),
                    "--lesson",
                    "Preserve release validation commands in maintainer guidance.",
                    "--lesson",
                    "temporary scratch note from this session",
                    "--json",
                ],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)

        self.assertEqual(payload["format"], "sejong.repo-context-candidate/v0.1-draft")
        self.assertEqual(payload["action"], "create")
        self.assertFalse((repo_root / "AGENTS.md").exists())
        self.assertEqual(payload["accepted_lessons"], ["Preserve release validation commands in maintainer guidance."])
        self.assertEqual(payload["rejected_lessons"][0]["reason"], "contains transient term: this session")
        self.assertIn("read_only_candidate", payload["write_policy"])


if __name__ == "__main__":
    unittest.main()
