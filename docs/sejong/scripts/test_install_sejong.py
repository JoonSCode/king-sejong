#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
INSTALLER = REPO_ROOT / "scripts" / "install-sejong.sh"


def run_installer(args: list[str], *, codex_home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


class InstallSejongTests(unittest.TestCase):
    def test_print_codex_guidance_is_generic_and_omx_free(self) -> None:
        result = run_installer(["--print-codex-guidance"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("King Sejong Codex Guidance", result.stdout)
        self.assertIn("Do not use `.omx` paths as Sejong state.", result.stdout)
        self.assertNotIn("oh-my-codex", result.stdout.lower())

    def test_user_scope_codex_guidance_writes_managed_agents_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "user"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            agents_path = codex_home / "AGENTS.md"
            self.assertTrue(agents_path.exists())
            text = agents_path.read_text(encoding="utf-8")
            self.assertIn("BEGIN King Sejong Codex Guidance", text)
            self.assertIn("END King Sejong Codex Guidance", text)
            self.assertIn("Do not use `.omx` paths as Sejong state.", text)
            self.assertNotIn("This repository is both the source repository", text)

    def test_invalid_codex_guidance_mode_fails(self) -> None:
        result = run_installer(["--codex-guidance", "sideways"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported codex guidance mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
