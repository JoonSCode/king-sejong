#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


IDENTITY_FORMAT = "sejong.core-install-identity/v0.1"
CHECK_FORMAT = "sejong.core-install-identity-check/v0.1"
CONTRACT_VERSION = "0.1.0"
IDENTITY_RELATIVE_PATH = Path("state/core-install-identity.json")
AUTHORITY_EXCLUSIONS = ["routing", "approval", "execution", "verification"]

SOURCE_MANAGED_SURFACES = (
    ".agents/skills/sejong",
    ".agents/skills/jangyeongsil",
    ".agents/skills/jiphyeonjeon",
    ".agents/skills/uigwe",
    ".agents/skills/seungjeongwon",
    ".agents/skills/why-gate",
    "docs/sejong",
    "plugins/king-sejong",
)

INSTALLED_MANAGED_SURFACES = (
    "skills/sejong",
    "skills/jangyeongsil",
    "skills/jiphyeonjeon",
    "skills/uigwe",
    "skills/seungjeongwon",
    "skills/why-gate",
    "plugins/cache/king-sejong-local/king-sejong/0.1.0",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_IGNORED_NAMES = {".DS_Store", "__pycache__"}
_VERIFICATION_EVIDENCE = [
    {"check": "source_managed_content_hashed", "status": "passed"},
    {"check": "installed_managed_content_hashed", "status": "passed"},
]


class IdentityInputError(ValueError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_relative_path(relative_path: str) -> None:
    path = PurePosixPath(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        raise IdentityInputError(f"managed surface path must be relative: {relative_path!r}")


def _ignored(path: Path, surface_root: Path) -> bool:
    relative = path.relative_to(surface_root)
    return any(part in _IGNORED_NAMES for part in relative.parts)


def _surface_digest(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        raise IdentityInputError(f"managed surface is missing: {path}")

    entries: list[dict[str, str]] = []
    if path.is_symlink():
        entries.append({"kind": "symlink", "path": ".", "value": os.readlink(path)})
    elif path.is_file():
        entries.append({"kind": "file", "path": ".", "sha256": _file_sha256(path)})
    elif path.is_dir():
        candidates = sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix())
        for candidate in candidates:
            if _ignored(candidate, path):
                continue
            relative = candidate.relative_to(path).as_posix()
            if candidate.is_symlink():
                entries.append({"kind": "symlink", "path": relative, "value": os.readlink(candidate)})
            elif candidate.is_file():
                entries.append({"kind": "file", "path": relative, "sha256": _file_sha256(candidate)})
    else:
        raise IdentityInputError(f"managed surface has unsupported type: {path}")

    return _canonical_sha256(
        {
            "algorithm": "sejong-managed-surface-sha256/v1",
            "entries": entries,
        }
    )


def snapshot_managed_surfaces(root: Path | str, surfaces: Sequence[str]) -> dict[str, Any]:
    resolved_root = Path(root).expanduser().resolve()
    records: list[dict[str, str]] = []
    for relative_path in surfaces:
        _validate_relative_path(relative_path)
        records.append(
            {
                "relative_path": relative_path,
                "sha256": _surface_digest(resolved_root / relative_path),
            }
        )
    records.sort(key=lambda item: item["relative_path"])
    return {
        "managed_content_sha256": _canonical_sha256(
            {
                "algorithm": "sejong-managed-content-sha256/v1",
                "surfaces": records,
            }
        ),
        "surfaces": records,
    }


def discover_source_git_identity(source_root: Path | str) -> tuple[str, str]:
    root = Path(source_root).expanduser().resolve()
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise IdentityInputError(f"cannot inspect source git identity: {root}") from exc
    if not _COMMIT_RE.fullmatch(commit):
        raise IdentityInputError(f"unsupported source commit identity: {commit!r}")
    return commit, "dirty" if status else "clean"


def _normalized_timestamp(value: str | None) -> str:
    timestamp = (
        value
        if value is not None
        else datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IdentityInputError(f"generated_at must be an RFC 3339 timestamp: {timestamp!r}") from exc
    if parsed.tzinfo is None:
        raise IdentityInputError("generated_at must include a timezone")
    return timestamp


def _identity_basis(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": identity["format"],
        "contract_version": identity["contract_version"],
        "source": identity["source"],
        "installed": identity["installed"],
    }


def _expected_managed_content_sha256(surfaces: list[dict[str, str]]) -> str:
    return _canonical_sha256(
        {
            "algorithm": "sejong-managed-content-sha256/v1",
            "surfaces": surfaces,
        }
    )


def create_identity(
    source_root: Path | str,
    installed_root: Path | str,
    *,
    source_commit: str | None = None,
    source_tree_state: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if source_commit is None or source_tree_state is None:
        discovered_commit, discovered_state = discover_source_git_identity(source_root)
        source_commit = source_commit or discovered_commit
        source_tree_state = source_tree_state or discovered_state
    if not _COMMIT_RE.fullmatch(source_commit):
        raise IdentityInputError(f"unsupported source commit identity: {source_commit!r}")
    if source_tree_state not in {"clean", "dirty"}:
        raise IdentityInputError(f"unsupported source tree state: {source_tree_state!r}")

    source = snapshot_managed_surfaces(source_root, SOURCE_MANAGED_SURFACES)
    source["commit"] = source_commit
    source["tree_state"] = source_tree_state
    installed = snapshot_managed_surfaces(installed_root, INSTALLED_MANAGED_SURFACES)
    identity: dict[str, Any] = {
        "format": IDENTITY_FORMAT,
        "contract_version": CONTRACT_VERSION,
        "generated_at": _normalized_timestamp(generated_at),
        "source": source,
        "installed": installed,
        "verification_evidence": list(_VERIFICATION_EVIDENCE),
        "authority": "provenance_only",
        "authority_exclusions": list(AUTHORITY_EXCLUSIONS),
    }
    identity["identity_sha256"] = _canonical_sha256(_identity_basis(identity))
    errors = validate_identity_contract(identity)
    if errors:
        raise IdentityInputError(f"generated identity is invalid: {', '.join(errors)}")
    return identity


def _valid_surfaces(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    paths: list[str] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"relative_path", "sha256"}:
            return False
        relative_path = item.get("relative_path")
        digest = item.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            return False
        try:
            _validate_relative_path(relative_path)
        except IdentityInputError:
            return False
        paths.append(relative_path)
    return paths == sorted(paths) and len(paths) == len(set(paths))


def _valid_managed_identity(value: Any, *, source: bool) -> bool:
    required = {"managed_content_sha256", "surfaces"}
    if source:
        required |= {"commit", "tree_state"}
    if not isinstance(value, dict) or set(value) != required:
        return False
    digest = value.get("managed_content_sha256")
    surfaces = value.get("surfaces")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest) or not _valid_surfaces(surfaces):
        return False
    if digest != _expected_managed_content_sha256(surfaces):
        return False
    if source:
        commit = value.get("commit")
        if not isinstance(commit, str) or not _COMMIT_RE.fullmatch(commit):
            return False
        if value.get("tree_state") not in {"clean", "dirty"}:
            return False
    return True


def validate_identity_contract(identity: Any) -> list[str]:
    if not isinstance(identity, dict):
        return ["identity_not_object"]
    expected_fields = {
        "format",
        "contract_version",
        "generated_at",
        "source",
        "installed",
        "identity_sha256",
        "verification_evidence",
        "authority",
        "authority_exclusions",
    }
    errors: list[str] = []
    if set(identity) != expected_fields:
        errors.append("identity_fields_invalid")
    if identity.get("format") != IDENTITY_FORMAT:
        errors.append("identity_format_invalid")
    if identity.get("contract_version") != CONTRACT_VERSION:
        errors.append("identity_contract_version_invalid")
    generated_at = identity.get("generated_at")
    try:
        if not isinstance(generated_at, str):
            raise IdentityInputError("generated_at must be a string")
        _normalized_timestamp(generated_at)
    except IdentityInputError:
        errors.append("identity_generated_at_invalid")
    if not _valid_managed_identity(identity.get("source"), source=True):
        errors.append("identity_source_invalid")
    if not _valid_managed_identity(identity.get("installed"), source=False):
        errors.append("identity_installed_invalid")
    if identity.get("verification_evidence") != _VERIFICATION_EVIDENCE:
        errors.append("identity_verification_evidence_invalid")
    if identity.get("authority") != "provenance_only":
        errors.append("identity_authority_invalid")
    if identity.get("authority_exclusions") != AUTHORITY_EXCLUSIONS:
        errors.append("identity_authority_exclusions_invalid")
    digest = identity.get("identity_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        errors.append("identity_sha256_invalid")
    elif not any(
        item in errors
        for item in (
            "identity_fields_invalid",
            "identity_format_invalid",
            "identity_contract_version_invalid",
            "identity_source_invalid",
            "identity_installed_invalid",
        )
    ):
        if digest != _canonical_sha256(_identity_basis(identity)):
            errors.append("identity_sha256_mismatch")
    return errors


def write_identity(path: Path | str, identity: dict[str, Any]) -> None:
    errors = validate_identity_contract(identity)
    if errors:
        raise IdentityInputError(f"refusing to write invalid identity: {', '.join(errors)}")
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        os.replace(temporary_path, output)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _check_result(
    *,
    status: str,
    errors: Iterable[str],
    identity_sha256: str | None,
    identity_present: bool,
    identity_well_formed: bool,
    source_matches: bool | None,
    installed_matches: bool | None,
) -> dict[str, Any]:
    return {
        "format": CHECK_FORMAT,
        "status": status,
        "identity_sha256": identity_sha256,
        "checks": {
            "identity_present": identity_present,
            "identity_well_formed": identity_well_formed,
            "source_matches": source_matches,
            "installed_matches": installed_matches,
        },
        "errors": list(errors),
        "authority": "provenance_only",
    }


def inspect_identity(
    identity_path: Path | str,
    *,
    source_root: Path | str | None = None,
    installed_root: Path | str | None = None,
    source_commit: str | None = None,
    source_tree_state: str | None = None,
) -> dict[str, Any]:
    path = Path(identity_path).expanduser().resolve()
    if not path.is_file():
        return _check_result(
            status="missing",
            errors=["identity_missing"],
            identity_sha256=None,
            identity_present=False,
            identity_well_formed=False,
            source_matches=None,
            installed_matches=None,
        )
    try:
        identity = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _check_result(
            status="malformed",
            errors=["identity_json_invalid", "identity_contract_invalid"],
            identity_sha256=None,
            identity_present=True,
            identity_well_formed=False,
            source_matches=None,
            installed_matches=None,
        )
    contract_errors = validate_identity_contract(identity)
    if contract_errors:
        return _check_result(
            status="malformed",
            errors=["identity_contract_invalid", *contract_errors],
            identity_sha256=identity.get("identity_sha256") if isinstance(identity, dict) else None,
            identity_present=True,
            identity_well_formed=False,
            source_matches=None,
            installed_matches=None,
        )

    errors: list[str] = []
    source_matches: bool | None = None
    installed_matches: bool | None = None
    if source_root is not None:
        if source_commit is None or source_tree_state is None:
            try:
                discovered_commit, discovered_state = discover_source_git_identity(source_root)
            except IdentityInputError:
                discovered_commit, discovered_state = None, None
                errors.append("source_git_identity_unavailable")
            source_commit = source_commit or discovered_commit
            source_tree_state = source_tree_state or discovered_state
        try:
            current_source = snapshot_managed_surfaces(source_root, SOURCE_MANAGED_SURFACES)
        except IdentityInputError:
            current_source = None
            errors.append("source_managed_surface_unavailable")
        source_matches = True
        if source_commit != identity["source"]["commit"]:
            source_matches = False
            errors.append("source_commit_mismatch")
        if source_tree_state != identity["source"]["tree_state"]:
            source_matches = False
            errors.append("source_tree_state_mismatch")
        if current_source is None:
            source_matches = False
        else:
            if current_source["managed_content_sha256"] != identity["source"]["managed_content_sha256"]:
                source_matches = False
                errors.append("source_managed_content_mismatch")
            if current_source["surfaces"] != identity["source"]["surfaces"]:
                source_matches = False
                errors.append("source_surface_manifest_mismatch")

    if installed_root is not None:
        try:
            current_installed = snapshot_managed_surfaces(installed_root, INSTALLED_MANAGED_SURFACES)
        except IdentityInputError:
            current_installed = None
            errors.append("installed_managed_surface_unavailable")
        installed_matches = True
        if current_installed is None:
            installed_matches = False
        else:
            if current_installed["managed_content_sha256"] != identity["installed"]["managed_content_sha256"]:
                installed_matches = False
                errors.append("installed_managed_content_mismatch")
            if current_installed["surfaces"] != identity["installed"]["surfaces"]:
                installed_matches = False
                errors.append("installed_surface_manifest_mismatch")

    if source_matches is False:
        status = "source_drift"
    elif installed_matches is False:
        status = "installed_tampered"
    else:
        status = "compatible"
    return _check_result(
        status=status,
        errors=errors,
        identity_sha256=identity["identity_sha256"],
        identity_present=True,
        identity_well_formed=True,
        source_matches=source_matches,
        installed_matches=installed_matches,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or inspect a provenance-only King Sejong install identity.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    write_parser = subparsers.add_parser("write", help="Write an installed Core identity atomically.")
    write_parser.add_argument("--source-root", required=True)
    write_parser.add_argument("--installed-root", required=True)
    write_parser.add_argument("--output", required=True)
    write_parser.add_argument("--source-commit")
    write_parser.add_argument("--source-tree-state", choices=("clean", "dirty"))
    write_parser.add_argument("--generated-at")

    verify_parser = subparsers.add_parser("verify", help="Inspect an identity without writing.")
    verify_parser.add_argument("--identity", required=True)
    verify_parser.add_argument("--source-root")
    verify_parser.add_argument("--installed-root")
    verify_parser.add_argument("--source-commit")
    verify_parser.add_argument("--source-tree-state", choices=("clean", "dirty"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "write":
            identity = create_identity(
                args.source_root,
                args.installed_root,
                source_commit=args.source_commit,
                source_tree_state=args.source_tree_state,
                generated_at=args.generated_at,
            )
            write_identity(args.output, identity)
            print(
                json.dumps(
                    {
                        "status": "written",
                        "output": str(Path(args.output).expanduser().resolve()),
                        "identity_sha256": identity["identity_sha256"],
                        "authority": "provenance_only",
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            return 0

        result = inspect_identity(
            args.identity,
            source_root=args.source_root,
            installed_root=args.installed_root,
            source_commit=args.source_commit,
            source_tree_state=args.source_tree_state,
        )
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0 if result["status"] == "compatible" else 1
    except IdentityInputError as exc:
        print(
            json.dumps(
                {
                    "format": CHECK_FORMAT,
                    "status": "malformed",
                    "errors": ["identity_input_invalid", str(exc)],
                    "authority": "provenance_only",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
