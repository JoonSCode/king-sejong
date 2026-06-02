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
    "validation_task_set": SEJONG_ROOT / "validation.task-set.schema.json",
    "validation_scorecard": SEJONG_ROOT / "validation.scorecard.schema.json",
    "king_sejong_context": SEJONG_ROOT / "king-sejong-context.schema.json",
    "ambiguity_register": SEJONG_ROOT / "ambiguity-register.schema.json",
    "team_executor": SEJONG_ROOT / "team-executor.schema.json",
    "continuity_capsule": SEJONG_ROOT / "continuity-capsule.schema.json",
    "seungjeongwon_run": SEJONG_ROOT / "seungjeongwon-run.schema.json",
    "workflow_run": SEJONG_ROOT / "workflow-run.schema.json",
    "outcome_quality": SEJONG_ROOT / "outcome-quality.schema.json",
    "product_evidence": SEJONG_ROOT / "product-evidence.schema.json",
    "sillok_trace_event": SEJONG_ROOT / "sillok-trace-event.schema.json",
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
    "uigwe.validation-task-set/v0.1-draft": "validation_task_set",
    "uigwe.validation-scorecard/v0.1-draft": "validation_scorecard",
    "king-sejong.context/v0.1-draft": "king_sejong_context",
    "sejong.ambiguity-register/v0.1-draft": "ambiguity_register",
    "sejong.team/v0.1-draft": "team_executor",
    "sejong.team-rounds/v0.1-draft": "team_executor",
    "sejong.team-leases/v0.1-draft": "team_executor",
    "sejong.team-worker/v0.1-draft": "team_executor",
    "sejong.team-mailbox-message/v0.1-draft": "team_executor",
    "sejong.team-mailbox-receive/v0.1-draft": "team_executor",
    "sejong.continuity-capsule/v0.1-draft": "continuity_capsule",
    "sejong.seungjeongwon-run/v0.1-draft": "seungjeongwon_run",
    "sejong.workflow-run/v0.1-draft": "workflow_run",
    "sejong.outcome-quality-task/v0.1-draft": "outcome_quality",
    "sejong.outcome-quality-result/v0.1-draft": "outcome_quality",
    "sejong.outcome-quality-comparison/v0.1-draft": "outcome_quality",
    "sejong.long-session-experiment-gate/v0.1-draft": "outcome_quality",
    "sejong.blind-semantic-packet/v0.1-draft": "outcome_quality",
    "sejong.blind-semantic-key/v0.1-draft": "outcome_quality",
    "sejong.blind-semantic-judgment/v0.1-draft": "outcome_quality",
    "sejong.blind-semantic-gate/v0.1-draft": "outcome_quality",
    "sejong.product-evidence-plan/v0.1-draft": "product_evidence",
    "sejong.product-evidence-result/v0.1-draft": "product_evidence",
    "sejong.product-evidence-judgment/v0.1-draft": "product_evidence",
    "sejong.sillok-trace-event/v0.1-draft": "sillok_trace_event",
}

NEGATIVE_FIXTURE_PARTS = (
    "examples/team-executor/invalid-",
)


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
        relative_path = rel(path)

        try:
            data = load_json(path)
        except Exception as exc:
            failures.append((path, f"invalid JSON: {exc}"))
            continue

        if any(part in relative_path for part in NEGATIVE_FIXTURE_PARTS):
            skipped += 1
            print(f"skip: {relative_path} (negative fixture)")
            continue

        schema_name = FORMAT_TO_SCHEMA.get(data.get("format"))
        if not schema_name:
            skipped += 1
            print(f"skip: {relative_path} (no mapped schema for format {data.get('format')!r})")
            continue

        schema = schema_contents[schema_name]
        validator_cls = validators.validator_for(schema)
        validator = validator_cls(schema, registry=registry)
        try:
            validator.validate(data)
            validated += 1
            print(f"instance ok: {relative_path} -> {rel(SCHEMA_FILES[schema_name])}")
        except Exception as exc:
            failures.append((path, str(exc)))

    for path in sorted(SEJONG_ROOT.rglob("*.jsonl")):
        relative_path = rel(path)
        if any(part in relative_path for part in NEGATIVE_FIXTURE_PARTS):
            skipped += 1
            print(f"skip: {relative_path} (negative fixture)")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception as exc:
                failures.append((path, f"invalid JSONL at line {line_no}: {exc}"))
                continue
            schema_name = FORMAT_TO_SCHEMA.get(data.get("format"))
            if not schema_name:
                skipped += 1
                print(f"skip: {relative_path}:{line_no} (no mapped schema for format {data.get('format')!r})")
                continue
            schema = schema_contents[schema_name]
            validator_cls = validators.validator_for(schema)
            validator = validator_cls(schema, registry=registry)
            try:
                validator.validate(data)
                validated += 1
                print(f"instance ok: {relative_path}:{line_no} -> {rel(SCHEMA_FILES[schema_name])}")
            except Exception as exc:
                failures.append((path, f"line {line_no}: {exc}"))

    print(f"summary: schemas={len(schema_contents)} instances={validated} skipped={skipped} failures={len(failures)}")
    if failures:
        for path, message in failures:
            print(f"failure: {rel(path)} -> {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
