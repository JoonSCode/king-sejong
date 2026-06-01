#!/usr/bin/env python3
from __future__ import annotations

import os
import json
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
        self.assertIn("Always treat King Sejong as available", result.stdout)
        self.assertIn("Do not use `.omx` paths as Sejong state.", result.stdout)
        self.assertNotIn("oh-my-codex", result.stdout.lower())

    def test_user_scope_writes_managed_agents_guidance_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("AGENTS.md", result.stdout)
            agents_path = codex_home / "AGENTS.md"
            self.assertTrue(agents_path.exists())
            text = agents_path.read_text(encoding="utf-8")
            self.assertIn("BEGIN King Sejong Codex Guidance", text)
            self.assertIn("END King Sejong Codex Guidance", text)
            self.assertIn("Always treat King Sejong as available", text)
            self.assertIn("Do not use `.omx` paths as Sejong state.", text)
            self.assertNotIn("This repository is both the source repository", text)

    def test_user_scope_installs_codex_plugin_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            plugin_root = (
                codex_home
                / "plugins"
                / "cache"
                / "king-sejong-local"
                / "king-sejong"
                / "0.1.0"
            )
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            hooks_path = plugin_root / "hooks" / "hooks.json"
            hook_runner_path = plugin_root / "hooks" / "king-sejong-hook.py"
            plugin_skill_path = plugin_root / "skills" / "sejong" / "SKILL.md"
            marketplace_path = (
                codex_home
                / "plugins"
                / "cache"
                / "king-sejong-local"
                / ".agents"
                / "plugins"
                / "marketplace.json"
            )
            self.assertTrue(manifest_path.exists())
            self.assertTrue(hooks_path.exists())
            self.assertTrue(hook_runner_path.exists())
            self.assertTrue(marketplace_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "king-sejong")
            self.assertEqual(manifest["hooks"], "./hooks/hooks.json")
            self.assertNotIn("skills", manifest)
            self.assertFalse(plugin_skill_path.exists())

            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
            self.assertEqual(
                marketplace["plugins"],
                [
                    {
                        "name": "king-sejong",
                        "source": {"source": "local", "path": "./king-sejong/0.1.0"},
                    }
                ],
            )

            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertNotIn("# BEGIN King Sejong hooks", config)
            self.assertNotIn("king_sejong_hooks.py", config)
            self.assertIn("[marketplaces.king-sejong-local]", config)
            self.assertIn('source_type = "local"', config)
            self.assertIn('[plugins."king-sejong@king-sejong-local"]', config)
            self.assertIn("enabled = true", config)

            hook_result = subprocess.run(
                ["python3", str(hook_runner_path), "SessionStart"],
                input='{"source":"startup"}',
                text=True,
                capture_output=True,
                env={**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)},
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
            hook_payload = json.loads(hook_result.stdout)
            self.assertEqual(
                hook_payload["hookSpecificOutput"]["hookEventName"],
                "SessionStart",
            )
            self.assertIn(
                "King Sejong active context",
                hook_payload["hookSpecificOutput"]["additionalContext"],
            )

    def test_user_scope_force_migrates_legacy_direct_hooks_to_plugin_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            config_path = codex_home / "config.toml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                """
[features]
hooks = true

# BEGIN King Sejong hooks
[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = 'python3 "/old/king_sejong_hooks.py" Stop'
# END King Sejong hooks
""".lstrip(),
                encoding="utf-8",
            )

            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config = config_path.read_text(encoding="utf-8")
            self.assertNotIn("# BEGIN King Sejong hooks", config)
            self.assertNotIn("/old/king_sejong_hooks.py", config)
            self.assertIn('[plugins."king-sejong@king-sejong-local"]', config)

    def test_user_scope_legacy_direct_hooks_are_explicit_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force", "--legacy-direct-hooks"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("# BEGIN King Sejong hooks", config)
            self.assertIn("king_sejong_hooks.py", config)
            self.assertNotIn('[plugins."king-sejong@king-sejong-local"]', config)

            verify = run_installer(
                ["--scope", "user", "--verify", "--legacy-direct-hooks"],
                codex_home=codex_home,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_user_scope_verify_fails_when_direct_and_plugin_hooks_are_both_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config_path = codex_home / "config.toml"
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    """

# BEGIN King Sejong hooks
[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = 'python3 "/duplicate/king_sejong_hooks.py" Stop'
# END King Sejong hooks
"""
                )

            verify = run_installer(
                ["--scope", "user", "--verify"],
                codex_home=codex_home,
            )
            self.assertNotEqual(verify.returncode, 0)
            self.assertIn("duplicate King Sejong hook registration", verify.stderr)

    def test_user_scope_can_opt_out_of_codex_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((codex_home / "AGENTS.md").exists())

    def test_invalid_codex_guidance_mode_fails(self) -> None:
        result = run_installer(["--codex-guidance", "sideways"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported codex guidance mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
