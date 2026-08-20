#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:
    Draft202012Validator = None

from core_install_identity import (
    IDENTITY_RELATIVE_PATH,
    INSTALLED_MANAGED_SURFACES,
    SOURCE_MANAGED_SURFACES,
    create_identity,
    inspect_identity,
    validate_identity_contract,
    write_identity,
)


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
SCHEMA_PATH = SEJONG_ROOT / "core-install-identity.schema.json"
INSTALLER = REPO_ROOT / "scripts" / "install-sejong.sh"
SOURCE_COMMIT = "1" * 40
GENERATED_AT = "2026-08-20T00:00:00Z"


def populate_surfaces(root: Path, surfaces: tuple[str, ...], marker: str) -> None:
    for index, relative_path in enumerate(surfaces):
        path = root / relative_path
        path.mkdir(parents=True, exist_ok=True)
        (path / "payload.txt").write_text(
            f"{marker}:{index}:{relative_path}\n",
            encoding="utf-8",
        )


class CoreInstallIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source_root = self.root / "source"
        self.installed_root = self.root / "installed"
        populate_surfaces(self.source_root, SOURCE_MANAGED_SURFACES, "source")
        populate_surfaces(self.installed_root, INSTALLED_MANAGED_SURFACES, "installed")
        self.identity_path = self.root / "runtime" / IDENTITY_RELATIVE_PATH

    def create_fixture_identity(self, *, generated_at: str = GENERATED_AT) -> dict:
        identity = create_identity(
            self.source_root,
            self.installed_root,
            source_commit=SOURCE_COMMIT,
            source_tree_state="clean",
            generated_at=generated_at,
        )
        write_identity(self.identity_path, identity)
        return identity

    def inspect_fixture(self) -> dict:
        return inspect_identity(
            self.identity_path,
            source_root=self.source_root,
            installed_root=self.installed_root,
            source_commit=SOURCE_COMMIT,
            source_tree_state="clean",
        )

    def test_schema_accepts_generated_identity(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        identity = self.create_fixture_identity()

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["format"]["const"], identity["format"])
        self.assertEqual(validate_identity_contract(identity), [])
        if Draft202012Validator is not None:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(identity)

    def test_identity_digest_is_stable_across_generation_times(self) -> None:
        first = create_identity(
            self.source_root,
            self.installed_root,
            source_commit=SOURCE_COMMIT,
            source_tree_state="clean",
            generated_at="2026-08-20T00:00:00Z",
        )
        second = create_identity(
            self.source_root,
            self.installed_root,
            source_commit=SOURCE_COMMIT,
            source_tree_state="clean",
            generated_at="2026-08-20T00:01:00Z",
        )

        self.assertNotEqual(first["generated_at"], second["generated_at"])
        self.assertEqual(first["identity_sha256"], second["identity_sha256"])
        self.assertEqual(first["source"], second["source"])
        self.assertEqual(first["installed"], second["installed"])

    def test_missing_identity_is_reported_without_writing(self) -> None:
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        result = self.inspect_fixture()
        after = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))

        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["errors"], ["identity_missing"])
        self.assertEqual(before, after)

    def test_malformed_identity_is_reported(self) -> None:
        self.identity_path.parent.mkdir(parents=True, exist_ok=True)
        self.identity_path.write_text('{"format":"unexpected"}\n', encoding="utf-8")

        result = self.inspect_fixture()

        self.assertEqual(result["status"], "malformed")
        self.assertIn("identity_contract_invalid", result["errors"])

    def test_source_drift_is_reported(self) -> None:
        self.create_fixture_identity()
        target = self.source_root / SOURCE_MANAGED_SURFACES[0] / "payload.txt"
        target.write_text("changed source bytes\n", encoding="utf-8")

        result = self.inspect_fixture()

        self.assertEqual(result["status"], "source_drift")
        self.assertIn("source_managed_content_mismatch", result["errors"])
        self.assertTrue(result["checks"]["installed_matches"])

    def test_installed_tamper_is_reported(self) -> None:
        self.create_fixture_identity()
        target = self.installed_root / INSTALLED_MANAGED_SURFACES[0] / "payload.txt"
        target.write_text("tampered installed bytes\n", encoding="utf-8")

        result = self.inspect_fixture()

        self.assertEqual(result["status"], "installed_tampered")
        self.assertIn("installed_managed_content_mismatch", result["errors"])
        self.assertTrue(result["checks"]["source_matches"])

    def test_valid_identity_is_compatible_and_read_only(self) -> None:
        identity = self.create_fixture_identity()
        before = self.identity_path.read_bytes()

        result = self.inspect_fixture()

        self.assertEqual(result["status"], "compatible")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["identity_sha256"], identity["identity_sha256"])
        self.assertEqual(self.identity_path.read_bytes(), before)
        self.assertEqual(identity["authority"], "provenance_only")
        self.assertEqual(
            identity["authority_exclusions"],
            ["routing", "approval", "execution", "verification"],
        )


class CoreInstallIdentityInstallerTests(unittest.TestCase):
    def run_installer(
        self,
        args: list[str],
        *,
        codex_home: Path,
        sejong_home: Path,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "CODEX_HOME": str(codex_home),
            "SEJONG_HOME": str(sejong_home),
        }
        return subprocess.run(
            ["bash", str(INSTALLER), *args],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

    def test_isolated_user_install_emits_and_verifies_runtime_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            sejong_home = root / "sejong-runtime"

            install = self.run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )
            self.assertEqual(install.returncode, 0, install.stderr)

            identity_path = sejong_home / IDENTITY_RELATIVE_PATH
            self.assertTrue(identity_path.is_file())
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            self.assertEqual(identity["format"], "sejong.core-install-identity/v0.1")
            self.assertEqual(identity["authority"], "provenance_only")

            verify = self.run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertIn('"status":"compatible"', verify.stdout)

    def test_isolated_dry_run_does_not_write_runtime_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            sejong_home = root / "sejong-runtime"

            dry_run = self.run_installer(
                ["--scope", "user", "--force", "--dry-run", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )

            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertIn("would write Core install identity", dry_run.stdout)
            self.assertFalse((sejong_home / IDENTITY_RELATIVE_PATH).exists())

    def test_isolated_verify_rejects_installed_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            sejong_home = root / "sejong-runtime"
            install = self.run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            installed_skill = codex_home / "skills" / "sejong" / "SKILL.md"
            installed_skill.write_text("tampered installed bytes\n", encoding="utf-8")

            verify = self.run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )

            self.assertNotEqual(verify.returncode, 0)
            self.assertIn('"status":"installed_tampered"', verify.stdout)

    def test_isolated_verify_rejects_missing_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "codex"
            sejong_home = root / "sejong-runtime"
            install = self.run_installer(
                ["--scope", "user", "--force", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            (sejong_home / IDENTITY_RELATIVE_PATH).unlink()

            verify = self.run_installer(
                ["--scope", "user", "--verify", "--codex-guidance", "none"],
                codex_home=codex_home,
                sejong_home=sejong_home,
            )

            self.assertNotEqual(verify.returncode, 0)
            self.assertIn('"status":"missing"', verify.stdout)


if __name__ == "__main__":
    unittest.main()
