#!/usr/bin/env python3
from __future__ import annotations

import json
import fcntl
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
INSTALLER = REPO_ROOT / "scripts" / "install-sejong.sh"
PYTHON_RUNNER = REPO_ROOT / "docs" / "sejong" / "scripts" / "run_with_supported_python.sh"


def run_installer(
    args: list[str],
    *,
    codex_home: Path | None = None,
    extra_env: dict[str, str] | None = None,
    installer: Path = INSTALLER,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(installer), *args],
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


class InstallSejongTests(unittest.TestCase):
    def test_readmes_use_supported_python_runner_for_doctor(self) -> None:
        documented_command = (
            "bash docs/sejong/scripts/run_with_supported_python.sh "
            "docs/sejong/scripts/sejong_doctor.py"
        )
        for relative_path in ("README.md", "README.ko.md", "docs/sejong/README.md", "docs/sejong/DOCTOR.md"):
            with self.subTest(relative_path=relative_path):
                text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn(documented_command, text)
                self.assertNotIn("python3 docs/sejong/scripts/sejong_doctor.py", text)

    def test_public_python_runner_bootstraps_doctor_from_system_python(self) -> None:
        system_python = Path("/usr/bin/python3")
        uv_path = shutil.which("uv")
        if not system_python.exists() or uv_path is None:
            self.skipTest("system Python and uv are required for the compatibility path")
        version = subprocess.run(
            [str(system_python), "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            text=True,
            capture_output=True,
            check=True,
        )
        if tuple(int(part) for part in version.stdout.split()) >= (3, 11):
            self.skipTest("system Python already satisfies the documented runtime")

        result = subprocess.run(
            [
                "bash",
                str(PYTHON_RUNNER),
                str(REPO_ROOT / "docs" / "sejong" / "scripts" / "sejong_doctor.py"),
                "--help",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
            env={
                **os.environ,
                "PATH": os.pathsep.join((str(Path(uv_path).parent), "/usr/bin", "/bin")),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: sejong_doctor.py", result.stdout)

    def test_public_python_runner_accepts_newer_uv_managed_python(self) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("the test process must provide a supported fixture interpreter")
        bash_path = shutil.which("bash")
        if bash_path is None:
            self.skipTest("bash is required")
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp)
            fake_uv = fake_bin / "uv"
            fake_uv.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"python\" ] && [ \"$2\" = \"find\" ] && [ \"$3\" = \">=3.11\" ]; then\n"
                "  echo \"$SEJONG_TEST_UV_PYTHON\"\n"
                "  exit 0\n"
                "fi\n"
                "echo \"unexpected uv arguments: $*\" >&2\n"
                "exit 42\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)
            result = subprocess.run(
                [bash_path, str(PYTHON_RUNNER), "-c", "import sys; print(sys.version_info.minor)"],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
                env={
                    **os.environ,
                    "PATH": str(fake_bin),
                    "SEJONG_TEST_UV_PYTHON": sys.executable,
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(sys.version_info.minor))

    def test_user_install_bootstraps_supported_python_from_system_python(self) -> None:
        system_python = Path("/usr/bin/python3")
        uv_path = shutil.which("uv")
        if not system_python.exists() or uv_path is None:
            self.skipTest("system Python and uv are required for the compatibility path")
        version = subprocess.run(
            [str(system_python), "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            text=True,
            capture_output=True,
            check=True,
        )
        if tuple(int(part) for part in version.stdout.split()) >= (3, 11):
            self.skipTest("system Python already satisfies the installer runtime")

        restricted_path = os.pathsep.join((str(Path(uv_path).parent), "/usr/bin", "/bin"))
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            stable_source = temp_root / "source"
            shutil.copytree(
                REPO_ROOT,
                stable_source,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            codex_home = temp_root / "codex"
            installed = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                extra_env={"PATH": restricted_path},
                installer=stable_source / "scripts" / "install-sejong.sh",
            )
            verified = run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
                extra_env={"PATH": restricted_path},
                installer=stable_source / "scripts" / "install-sejong.sh",
            )
            installed_runner = codex_home / "skills" / "sejong" / "docs" / "scripts" / PYTHON_RUNNER.name
            installed_doctor = codex_home / "skills" / "sejong" / "docs" / "scripts" / "sejong_doctor.py"
            doctor_help = subprocess.run(
                ["bash", str(installed_runner), str(installed_doctor), "--help"],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PATH": restricted_path},
            )
            installed_skill = codex_home / "skills" / "sejong" / "SKILL.md"
            installed_skill.write_text(
                installed_skill.read_text(encoding="utf-8") + "\n# deterministic test drift\n",
                encoding="utf-8",
            )
            drifted = run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
                extra_env={"PATH": restricted_path},
                installer=stable_source / "scripts" / "install-sejong.sh",
            )

        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(doctor_help.returncode, 0, doctor_help.stderr)
        self.assertIn("usage: sejong_doctor.py", doctor_help.stdout)
        self.assertNotIn("managed content is stale or modified", verified.stderr)
        self.assertNotEqual(drifted.returncode, 0)
        self.assertIn("managed content is stale or modified", drifted.stderr)

    def test_installer_reports_unsupported_python_as_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            fake_bin = temp_root / "bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "  exit 1\n"
                "fi\n"
                "echo 'unsupported test interpreter' >&2\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            dirname_path = shutil.which("dirname")
            bash_path = shutil.which("bash")
            if dirname_path is None or bash_path is None:
                self.skipTest("bash and dirname are required")
            (fake_bin / "dirname").symlink_to(dirname_path)
            result = subprocess.run(
                [str(bash_path), str(INSTALLER), "--scope", "user", "--verify", "--codex-guidance", "none"],
                text=True,
                capture_output=True,
                cwd=str(REPO_ROOT),
                env={
                    **os.environ,
                    "CODEX_HOME": str(temp_root / "codex"),
                    "PATH": str(fake_bin),
                },
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires Python 3.11 or newer, or uv", result.stderr)
        self.assertNotIn("managed content is stale or modified", result.stderr)

    def test_print_codex_guidance_is_generic_and_external_runtime_free(self) -> None:
        result = run_installer(["--print-codex-guidance"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("King Sejong Codex Guidance", result.stdout)
        self.assertIn("Always treat King Sejong as available", result.stdout)
        self.assertIn("Do not use non-Sejong runtime paths as Sejong state.", result.stdout)
        self.assertIn("A complete brief is an output of Uigwe", result.stdout)
        self.assertIn("actual user path", result.stdout)
        self.assertIn("During an explicitly active Agent Company session", result.stdout)
        self.assertIn("This conditional Company rule does not activate Company", result.stdout)
        self.assertIn("distinguish settled scope from the remaining choice", result.stdout)
        self.assertIn("strongest counterargument", result.stdout)
        self.assertIn("ask for and wait for their explicit choice before dependent execution", result.stdout)
        self.assertIn("existing project assets", result.stdout)
        self.assertIn("without a search quota", result.stdout)
        self.assertIn("current user contract", result.stdout)

    def test_user_scope_replaces_only_managed_guidance_and_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            agents_path = codex_home / "AGENTS.md"
            user_before = "# 개인 작업 원칙\n자연스러운 한국어로 보고한다.\n"
            user_after = "# 모델 선택\n작업에 맞는 모델을 선택한다.\n"
            agents_path.write_text(
                user_before
                + "<!-- BEGIN King Sejong Codex Guidance -->\nobsolete managed text\n"
                + "<!-- END King Sejong Codex Guidance -->\n"
                + user_after,
                encoding="utf-8",
            )
            expected = run_installer(["--print-codex-guidance"])
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for _ in range(2):
                installed = run_installer(["--scope", "user", "--force"], codex_home=codex_home)
                self.assertEqual(installed.returncode, 0, installed.stderr)
                actual = agents_path.read_text(encoding="utf-8")
                self.assertIn(user_before, actual)
                self.assertIn(user_after, actual)
                self.assertNotIn("obsolete managed text", actual)
                self.assertEqual(actual.count("<!-- BEGIN King Sejong Codex Guidance -->"), 1)
                self.assertIn(expected.stdout.strip(), actual)

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
            self.assertIn("Do not use non-Sejong runtime paths as Sejong state.", text)
            self.assertIn("every ordinary prose final reply", text)
            self.assertIn("distinguish settled scope from the remaining choice", text)
            self.assertIn("existing project assets", text)
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
            plugin_why_gate_skill_path = plugin_root / "skills" / "why-gate" / "SKILL.md"
            why_gate_skill_path = codex_home / "skills" / "why-gate" / "SKILL.md"
            delegation_cli_path = codex_home / "skills" / "sejong" / "docs" / "scripts" / "delegation_run.py"
            delegation_validation_path = (
                codex_home / "skills" / "sejong" / "docs" / "scripts" / "delegation_wave_validation.py"
            )
            delegation_validation_test_path = (
                codex_home / "skills" / "sejong" / "docs" / "scripts" / "test_delegation_wave_validation.py"
            )
            action_cli_path = codex_home / "skills" / "sejong" / "docs" / "scripts" / "external_action_receipt.py"
            delegation_schema_path = codex_home / "skills" / "sejong" / "docs" / "delegation-run.schema.json"
            action_schema_path = codex_home / "skills" / "sejong" / "docs" / "external-action-receipt.schema.json"
            active_context_path = codex_home / "sejong" / "state" / "active-context.json"
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
            self.assertTrue(why_gate_skill_path.exists())
            self.assertTrue(delegation_cli_path.exists())
            self.assertTrue(delegation_validation_path.exists())
            self.assertTrue(delegation_validation_test_path.exists())
            self.assertTrue(action_cli_path.exists())
            self.assertTrue(delegation_schema_path.exists())
            self.assertTrue(action_schema_path.exists())
            self.assertFalse(active_context_path.exists())
            self.assertIn("Why Gate", why_gate_skill_path.read_text(encoding="utf-8"))

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], "king-sejong")
            self.assertEqual(manifest["hooks"], "./hooks/hooks.json")
            self.assertNotIn("skills", manifest)
            self.assertFalse(plugin_skill_path.exists())
            self.assertFalse(plugin_why_gate_skill_path.exists())

            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))["hooks"]
            self.assertIn("PreCompact", hooks)
            self.assertNotIn("PostCompact", hooks)
            self.assertEqual(hooks["SessionStart"][0]["matcher"], "startup|resume|compact")

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
            self.assertEqual(hook_result.stdout.strip(), "")

    def test_interrupted_user_install_publishes_fail_closed_maintenance_generation_first(self) -> None:
        # Given: an installed generation whose live canonical hook could inject legacy context.
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            initial = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            plugin_root = (
                codex_home
                / "plugins"
                / "cache"
                / "king-sejong-local"
                / "king-sejong"
                / "0.1.0"
            )
            hook_runner_path = plugin_root / "hooks" / "king-sejong-hook.py"
            canonical_hook_path = codex_home / "skills" / "sejong" / "docs" / "scripts" / "king_sejong_hooks.py"
            canonical_hook_path.write_text(
                "#!/usr/bin/env python3\nprint('LEGACY-CONTEXT-SHOULD-NOT-INJECT')\n",
                encoding="utf-8",
            )

            # When: installation stops immediately after its first authority mutation.
            interrupted = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                extra_env={"SEJONG_INSTALL_TEST_FAIL_AFTER_MAINTENANCE_GUARD": "1"},
            )
            transaction_path = codex_home / "sejong" / "state" / "install-transaction.json"
            transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
            hook_result = subprocess.run(
                ["python3", str(hook_runner_path), "UserPromptSubmit"],
                input='{"session_id":"unbound-after-interrupt","turn_id":"turn-interrupt"}',
                text=True,
                capture_output=True,
                env={**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)},
                cwd=str(REPO_ROOT),
            )

            # Then: the interrupted generation is quiet, and a normal rerun repairs it idempotently.
            self.assertNotEqual(interrupted.returncode, 0)
            self.assertEqual(transaction["status"], "in_progress")
            self.assertEqual(transaction["runtime_authority_epoch"], 2)
            self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
            self.assertEqual(hook_result.stdout, "")
            self.assertNotIn("LEGACY-CONTEXT-SHOULD-NOT-INJECT", hook_result.stdout)

            recovered = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            recovered_transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(recovered_transaction["status"], "complete")

    def test_user_install_crash_matrix_keeps_unbound_prompt_quiet_and_recovers(self) -> None:
        # Given: a complete V2 generation is installed before each deterministic crash point.
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            initial = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            for step in ("maintenance", "skills", "docs", "plugin", "config", "verified", "canonical"):
                with self.subTest(step=step):
                    interrupted = run_installer(
                        ["--scope", "user", "--force", "--codex-guidance", "none"],
                        codex_home=codex_home,
                        extra_env={"SEJONG_INSTALL_TEST_FAIL_AFTER_STEP": step},
                    )
                    plugin_root = (
                        codex_home
                        / "plugins"
                        / "cache"
                        / "king-sejong-local"
                        / "king-sejong"
                        / "0.1.0"
                    )
                    hook_runner_path = plugin_root / "hooks" / "king-sejong-hook.py"
                    hook_result = subprocess.run(
                        ["python3", str(hook_runner_path), "UserPromptSubmit"],
                        input=json.dumps(
                            {
                                "session_id": f"unbound-after-{step}",
                                "turn_id": f"turn-after-{step}",
                            }
                        ),
                        text=True,
                        capture_output=True,
                        env={**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)},
                        cwd=str(REPO_ROOT),
                    )
                    start_result = subprocess.run(
                        ["python3", str(hook_runner_path), "SessionStart"],
                        input=json.dumps(
                            {
                                "session_id": f"unbound-start-after-{step}",
                                "turn_id": f"turn-start-after-{step}",
                                "source": "startup",
                            }
                        ),
                        text=True,
                        capture_output=True,
                        env={**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)},
                        cwd=str(REPO_ROOT),
                    )

                    self.assertNotEqual(interrupted.returncode, 0)
                    self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
                    self.assertEqual(hook_result.stdout, "")
                    self.assertEqual(start_result.returncode, 0, start_result.stderr)
                    self.assertEqual(start_result.stdout, "")
                    canonical_hook_path = codex_home / "skills/sejong/docs/scripts/king_sejong_hooks.py"
                    if step != "canonical" and canonical_hook_path.exists():
                        self.assertIn("install maintenance is in progress", canonical_hook_path.read_text(encoding="utf-8"))

                    recovered = run_installer(
                        ["--scope", "user", "--force", "--codex-guidance", "none"],
                        codex_home=codex_home,
                    )
                    self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_user_install_uses_stable_exclusive_installer_lock_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            installed = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            canonical_hook_path = codex_home / "skills/sejong/docs/scripts/king_sejong_hooks.py"
            transaction_path = codex_home / "sejong/state/install-transaction.json"
            canonical_before = canonical_hook_path.read_bytes()
            transaction_before = transaction_path.read_bytes()
            lock_path = codex_home / "sejong/state/locks/user-install.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)

            with lock_path.open("a+") as held_lock:
                fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                contender = run_installer(
                    ["--scope", "user", "--force", "--codex-guidance", "none"],
                    codex_home=codex_home,
                    extra_env={"SEJONG_INSTALL_LOCK_TIMEOUT_SECONDS": "0.1"},
                )

            self.assertNotEqual(contender.returncode, 0)
            self.assertIn("user install lock", contender.stderr)
            self.assertEqual(canonical_hook_path.read_bytes(), canonical_before)
            self.assertEqual(transaction_path.read_bytes(), transaction_before)

            forged_bypass = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                extra_env={"SEJONG_INSTALL_LOCK_HELD": "1"},
            )
            self.assertNotEqual(forged_bypass.returncode, 0)
            self.assertIn("invalid inherited King Sejong user install lock", forged_bypass.stderr)
            self.assertEqual(canonical_hook_path.read_bytes(), canonical_before)
            self.assertEqual(transaction_path.read_bytes(), transaction_before)

    def test_epoch_two_install_rejects_supported_authority_downgrade_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            codex_home = temp_root / "codex"
            installed = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            canonical_hook_path = codex_home / "skills/sejong/docs/scripts/king_sejong_hooks.py"
            transaction_path = codex_home / "sejong/state/install-transaction.json"
            legacy_path = codex_home / "sejong/state/active-context.json"
            legacy_bytes = b'{"preserved":"legacy bytes"}\n'
            legacy_path.write_bytes(legacy_bytes)
            canonical_before = canonical_hook_path.read_bytes()
            transaction_before = transaction_path.read_bytes()

            downgrade_source = temp_root / "downgrade-source"
            shutil.copytree(
                REPO_ROOT,
                downgrade_source,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"),
            )
            downgrade_installer = downgrade_source / "scripts/install-sejong.sh"
            installer_text = downgrade_installer.read_text(encoding="utf-8")
            self.assertIn("RUNTIME_AUTHORITY_EPOCH=2", installer_text)
            downgrade_installer.write_text(
                installer_text.replace("RUNTIME_AUTHORITY_EPOCH=2", "RUNTIME_AUTHORITY_EPOCH=1", 1),
                encoding="utf-8",
            )

            rejected = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                installer=downgrade_installer,
            )

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Legacy-authority rollback is unsupported", rejected.stderr)
            self.assertEqual(canonical_hook_path.read_bytes(), canonical_before)
            self.assertEqual(transaction_path.read_bytes(), transaction_before)
            self.assertEqual(legacy_path.read_bytes(), legacy_bytes)

    def test_user_install_uses_frozen_source_snapshot_when_worktree_changes_mid_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            source_root = temp_root / "source"
            codex_home = temp_root / "codex"
            ready_path = temp_root / "snapshot.ready"
            release_path = temp_root / "snapshot.release"
            shutil.copytree(
                REPO_ROOT,
                source_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"),
            )
            source_canonical = source_root / "docs/sejong/scripts/king_sejong_hooks.py"
            canonical_snapshot = source_canonical.read_bytes()
            environment = {
                **os.environ,
                "CODEX_HOME": str(codex_home),
                "SEJONG_INSTALL_TEST_SNAPSHOT_READY_FILE": str(ready_path),
                "SEJONG_INSTALL_TEST_SNAPSHOT_RELEASE_FILE": str(release_path),
            }
            process = subprocess.Popen(
                [
                    "bash",
                    str(source_root / "scripts/install-sejong.sh"),
                    "--scope",
                    "user",
                    "--force",
                    "--codex-guidance",
                    "none",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(source_root),
                env=environment,
            )
            deadline = time.monotonic() + 10.0
            while not ready_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready_path.exists(), "installer did not publish the source snapshot barrier")

            source_canonical.write_bytes(canonical_snapshot + b"\n# mutation after frozen snapshot\n")
            release_path.write_text("release\n", encoding="utf-8")
            stdout, stderr = process.communicate(timeout=20)

            self.assertEqual(process.returncode, 0, stderr or stdout)
            installed_canonical = codex_home / "skills/sejong/docs/scripts/king_sejong_hooks.py"
            self.assertEqual(installed_canonical.read_bytes(), canonical_snapshot)
            transaction = json.loads(
                (codex_home / "sejong/state/install-transaction.json").read_text(encoding="utf-8")
            )
            self.assertEqual(transaction["status"], "complete")

    def test_mutating_child_retains_installer_lock_after_outer_owner_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            source_a = temp_root / "source-a"
            source_b = temp_root / "source-b"
            codex_home = temp_root / "codex"
            maintenance_ready = temp_root / "maintenance.ready"
            maintenance_release = temp_root / "maintenance.release"
            owner_pid_path = temp_root / "lock-owner.pid"
            mutator_pid_path = temp_root / "mutator.pid"
            for source in (source_a, source_b):
                shutil.copytree(
                    REPO_ROOT,
                    source,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"),
                )
            canonical_a = (source_a / "docs/sejong/scripts/king_sejong_hooks.py").read_bytes()
            canonical_b_path = source_b / "docs/sejong/scripts/king_sejong_hooks.py"
            canonical_b = canonical_b_path.read_bytes() + b"\n# distinct outer-death generation B\n"
            canonical_b_path.write_bytes(canonical_b)
            first_environment = {
                **os.environ,
                "CODEX_HOME": str(codex_home),
                "SEJONG_INSTALL_TEST_MAINTENANCE_READY_FILE": str(maintenance_ready),
                "SEJONG_INSTALL_TEST_MAINTENANCE_RELEASE_FILE": str(maintenance_release),
                "SEJONG_INSTALL_TEST_LOCK_OWNER_PID_FILE": str(owner_pid_path),
                "SEJONG_INSTALL_TEST_MUTATOR_PID_FILE": str(mutator_pid_path),
            }
            outer = subprocess.Popen(
                [
                    "bash",
                    str(source_a / "scripts/install-sejong.sh"),
                    "--scope",
                    "user",
                    "--force",
                    "--codex-guidance",
                    "none",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(source_a),
                env=first_environment,
            )
            owner_pid = 0
            mutator_pid = 0
            try:
                deadline = time.monotonic() + 12.0
                required = (maintenance_ready, owner_pid_path, mutator_pid_path)
                while not all(path.exists() for path in required) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(all(path.exists() for path in required), "first installer did not reach maintenance barrier")
                owner_pid = int(owner_pid_path.read_text(encoding="utf-8").strip())
                mutator_pid = int(mutator_pid_path.read_text(encoding="utf-8").strip())
                self.assertNotEqual(owner_pid, mutator_pid)
                os.kill(owner_pid, signal.SIGKILL)
                time.sleep(0.1)
                os.kill(mutator_pid, 0)

                blocked = run_installer(
                    ["--scope", "user", "--force", "--codex-guidance", "none"],
                    codex_home=codex_home,
                    installer=source_b / "scripts/install-sejong.sh",
                    extra_env={"SEJONG_INSTALL_LOCK_TIMEOUT_SECONDS": "0.2"},
                )
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn("user install lock", blocked.stderr)
                in_progress = json.loads(
                    (codex_home / "sejong/state/install-transaction.json").read_text(encoding="utf-8")
                )
                self.assertEqual(in_progress["status"], "in_progress")

                maintenance_release.write_text("release\n", encoding="utf-8")
                outer.communicate(timeout=20)
                completion_deadline = time.monotonic() + 10.0
                while time.monotonic() < completion_deadline:
                    transaction_path = codex_home / "sejong/state/install-transaction.json"
                    if transaction_path.exists():
                        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
                        if transaction.get("status") == "complete":
                            break
                    time.sleep(0.05)
                else:
                    self.fail("orphaned mutator did not complete generation A")
                installed_canonical = codex_home / "skills/sejong/docs/scripts/king_sejong_hooks.py"
                self.assertEqual(installed_canonical.read_bytes(), canonical_a)

                second = run_installer(
                    ["--scope", "user", "--force", "--codex-guidance", "none"],
                    codex_home=codex_home,
                    installer=source_b / "scripts/install-sejong.sh",
                )
                verified = run_installer(
                    ["--scope", "user", "--verify", "--codex-guidance", "none"],
                    codex_home=codex_home,
                    installer=source_b / "scripts/install-sejong.sh",
                )
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertEqual(verified.returncode, 0, verified.stderr)
                self.assertEqual(installed_canonical.read_bytes(), canonical_b)
            finally:
                maintenance_release.write_text("release\n", encoding="utf-8")
                if outer.poll() is None:
                    try:
                        outer.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        outer.kill()
                        outer.communicate(timeout=5)
                if mutator_pid:
                    try:
                        os.kill(mutator_pid, 0)
                    except ProcessLookupError:
                        pass
                    else:
                        os.kill(mutator_pid, signal.SIGKILL)

    def test_plugin_adapter_fails_closed_when_installed_authority_digest_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            installed = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            plugin_root = (
                codex_home
                / "plugins"
                / "cache"
                / "king-sejong-local"
                / "king-sejong"
                / "0.1.0"
            )
            hook_runner_path = plugin_root / "hooks" / "king-sejong-hook.py"
            canonical_hook_path = codex_home / "skills" / "sejong" / "docs" / "scripts" / "king_sejong_hooks.py"
            canonical_hook_path.write_text(
                canonical_hook_path.read_text(encoding="utf-8") + "\n# deterministic digest drift\n",
                encoding="utf-8",
            )
            env = {**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)}

            prompt_result = subprocess.run(
                ["python3", str(hook_runner_path), "UserPromptSubmit"],
                input='{"session_id":"unbound-drift","turn_id":"turn-drift"}',
                text=True,
                capture_output=True,
                env=env,
                cwd=str(REPO_ROOT),
            )
            protected_result = subprocess.run(
                ["python3", str(hook_runner_path), "PreToolUse"],
                input='{"session_id":"unbound-drift","turn_id":"turn-drift"}',
                text=True,
                capture_output=True,
                env=env,
                cwd=str(REPO_ROOT),
            )

            self.assertEqual(prompt_result.returncode, 0, prompt_result.stderr)
            self.assertEqual(prompt_result.stdout, "")
            self.assertEqual(protected_result.returncode, 127)
            self.assertIn("runtime authority digest mismatch", protected_result.stderr)

    def test_plugin_adapter_surfaces_missing_canonical_hook_for_protected_event(self) -> None:
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
            hook_runner_path = plugin_root / "hooks" / "king-sejong-hook.py"
            canonical_hook_path = codex_home / "skills" / "sejong" / "docs" / "scripts" / "king_sejong_hooks.py"
            canonical_hook_path.unlink()

            hook_result = subprocess.run(
                ["python3", str(hook_runner_path), "PreToolUse"],
                input='{"tool_name":"apply_patch"}',
                text=True,
                capture_output=True,
                env={**os.environ, "CODEX_HOME": str(codex_home), "PLUGIN_ROOT": str(plugin_root)},
                cwd=str(REPO_ROOT),
            )

        self.assertNotEqual(hook_result.returncode, 0)
        self.assertIn("missing King Sejong canonical hook script", hook_result.stderr)

    def test_plugin_adapter_bootstraps_supported_python_from_system_interpreter(self) -> None:
        system_python = Path("/usr/bin/python3")
        if not system_python.exists():
            self.skipTest("system Python is unavailable")
        version = subprocess.run(
            [str(system_python), "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            text=True,
            capture_output=True,
            check=True,
        )
        system_version = tuple(int(part) for part in version.stdout.split())
        if system_version >= (3, 11):
            self.skipTest("system Python already satisfies the canonical script runtime")
        uv_path = shutil.which("uv")
        if uv_path is None:
            self.skipTest("uv is unavailable for the compatibility bootstrap")

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            hook_runner_path = (
                codex_home
                / "plugins"
                / "cache"
                / "king-sejong-local"
                / "king-sejong"
                / "0.1.0"
                / "hooks"
                / "king-sejong-hook.py"
            )

            hook_result = subprocess.run(
                [str(system_python), str(hook_runner_path), "SessionStart"],
                input='{"source":"startup"}',
                text=True,
                capture_output=True,
                env={
                    **os.environ,
                    "CODEX_HOME": str(codex_home),
                    "PATH": os.pathsep.join((str(Path(uv_path).parent), "/usr/bin", "/bin")),
                },
                cwd=str(REPO_ROOT),
            )
            bytecode_cache = codex_home / "skills" / "sejong" / "docs" / "scripts" / "__pycache__"
            cache_exists = bytecode_cache.exists()

        self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
        self.assertEqual(hook_result.stdout, "")
        self.assertFalse(cache_exists)

    def test_user_scope_install_does_not_mutate_existing_active_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            context_path = codex_home / "sejong" / "state" / "active-context.json"
            context_path.parent.mkdir(parents=True)
            original_context = {
                "format": "king-sejong.context/v0.1-draft",
                "active_context_id": "ctx-user-workflow",
                "repo_id": "user-workflow",
                "repo_root": "/tmp/user-workflow",
                "run_id": "run-user-workflow",
                "session_id": "session-user-workflow",
                "route_id": "route-user-workflow",
                "current_surface": "sejong",
                "route_sequence": ["sejong"],
                "required_route_sequence": [],
                "last_user_intent": "Existing user workflow.",
                "pending_gates": [],
                "protected_paths": ["user-owned-path"],
                "allowed_direct_change_types": [],
                "evidence_refs": [],
                "artifact_refs": [],
                "team_run_refs": [],
                "subagent_refs": [],
                "exit_conditions": ["user_explicitly_exits_sejong"],
                "last_updated_at": "2026-06-20T00:00:00Z",
            }
            context_path.write_text(json.dumps(original_context, indent=2) + "\n", encoding="utf-8")

            result = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(context_path.read_text(encoding="utf-8")), original_context)

    def test_user_scope_force_removes_stale_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            initial = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            stale_cache = (
                codex_home
                / "skills"
                / "sejong"
                / "docs"
                / "scripts"
                / "__pycache__"
                / "stale.cpython-311.pyc"
            )
            stale_cache.parent.mkdir()
            stale_cache.write_bytes(b"stale")

            reinstalled = run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
            )

            cache_exists = stale_cache.parent.exists()
        self.assertEqual(reinstalled.returncode, 0, reinstalled.stderr)
        self.assertFalse(cache_exists)

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
            self.assertIn("king-sejong-hook.py", config)
            self.assertNotIn("king_sejong_hooks.py", config)
            self.assertIn("[[hooks.PreCompact]]", config)
            self.assertNotIn("[[hooks.PostCompact]]", config)
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

            verify = run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_invalid_codex_guidance_mode_fails(self) -> None:
        result = run_installer(["--codex-guidance", "sideways"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported codex guidance mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
