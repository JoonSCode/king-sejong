#!/usr/bin/env python3
from __future__ import annotations

import json
import site
import sys
from pathlib import Path

user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.append(user_site)

from jsonschema import validators
from referencing import Registry, Resource


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]

SCHEMA_FILES = {
    "packets": SEJONG_ROOT / "packets.schema.json",
    "goal_tree": SEJONG_ROOT / "goal-tree.schema.json",
    "wrapper": SEJONG_ROOT / "wrapper.schema.json",
    "consumer_feedback": SEJONG_ROOT / "codex-consumer-feedback.schema.json",
    "consumer_dry_run": SEJONG_ROOT / "consumer-dry-run-result.schema.json",
    "policy_defaults": SEJONG_ROOT / "policy.defaults.schema.json",
}

FORMAT_TO_SCHEMA = {
    "uigwe.intent-packet/v0.1-draft": "packets",
    "uigwe.design-packet/v0.1-draft": "packets",
    "uigwe.plan-packet/v0.1-draft": "packets",
    "uigwe.goal-tree/v0.1-draft": "goal_tree",
    "uigwe.wrapper-request/v0.1-draft": "wrapper",
    "uigwe.wrapper-result/v0.1-draft": "wrapper",
    "uigwe.codex-consumer-feedback/v0.2-draft": "consumer_feedback",
    "uigwe.consumer-dry-run-result/v0.1-draft": "consumer_dry_run",
    "uigwe.policy-defaults/v0.1-draft": "policy_defaults",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_registry(schema_contents: dict[str, dict]) -> Registry:
    resources = []
    for schema in schema_contents.values():
        schema_id = schema.get("$id")
        if not schema_id:
            raise ValueError("Schema missing $id")
        resources.append((schema_id, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def rel(path: Path) -> str:
    return str(path.relative_to(SEJONG_ROOT))


def main() -> int:
    schema_contents = {name: load_json(path) for name, path in SCHEMA_FILES.items()}
    registry = build_registry(schema_contents)

    for name, schema in schema_contents.items():
        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        print(f"schema ok: {rel(SCHEMA_FILES[name])}")

    validated = 0
    skipped = 0
    failures: list[tuple[Path, str]] = []

    for path in sorted(SEJONG_ROOT.rglob("*.json")):
        if path.name.endswith(".schema.json"):
            continue

        try:
            data = load_json(path)
        except Exception as exc:
            failures.append((path, f"invalid JSON: {exc}"))
            continue

        schema_name = FORMAT_TO_SCHEMA.get(data.get("format"))
        if not schema_name:
            skipped += 1
            print(f"skip: {rel(path)} (no mapped schema for format {data.get('format')!r})")
            continue

        schema = schema_contents[schema_name]
        validator_cls = validators.validator_for(schema)
        validator = validator_cls(schema, registry=registry)
        try:
            validator.validate(data)
            validated += 1
            print(f"instance ok: {rel(path)} -> {rel(SCHEMA_FILES[schema_name])}")
        except Exception as exc:
            failures.append((path, str(exc)))

    print(f"summary: schemas={len(schema_contents)} instances={validated} skipped={skipped} failures={len(failures)}")
    if failures:
        for path, message in failures:
            print(f"failure: {rel(path)} -> {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
