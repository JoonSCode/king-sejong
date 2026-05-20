# Uigwe Bundle Validator

**Status:** Draft

## Purpose

The Uigwe bundle validator is the first v0.2 implementation priority.

Its job is to validate not only individual JSON files, but the **bundle as a bundle**.

Current implementation draft:

- `scripts/validate_bundle.py`

This exists because schema-valid planning is not enough if:

- fields drift into the wrong artifact
- the resolved mode and generated artifact set disagree
- wrapper outputs point at missing files
- packets and goal trees are individually valid but collectively inconsistent

## What It Validates

The validator works on one Uigwe run directory at a time.

Example input directory:

- `docs/sejong/examples/greenfield-full-flow/`

It should validate:

### 1. File Presence By Mode

Given `wrapper.result.json.resolved_mode`, confirm the correct artifact set exists.

Rules:

- `full`
  - must include:
    - `wrapper.request.json`
    - `wrapper.result.json`
    - `intent.packet.json`
    - `design.packet.json`
    - `plan.packet.json`
    - `goal-tree.json`
    - `spec.md`
    - `rationale.md`
- `design-to-plan`
  - must include:
    - `wrapper.request.json`
    - `wrapper.result.json`
    - `design.packet.json`
    - `plan.packet.json`
    - `goal-tree.json`
    - `spec.md`
    - `rationale.md`
  - must not require:
    - `intent.packet.json`
- `decompose-only`
  - must include:
    - `wrapper.request.json`
    - `wrapper.result.json`
    - `plan.packet.json`
    - `goal-tree.json`
    - `spec.md`
    - `rationale.md`
  - must not require:
    - `intent.packet.json`
    - `design.packet.json`

### 2. Per-File Schema Validity

Validate:

- `wrapper.request.json` and `wrapper.result.json` against `wrapper.schema.json`
- `intent.packet.json`, `design.packet.json`, `plan.packet.json` against `packets.schema.json`
- `goal-tree.json` against `goal-tree.schema.json`

### 3. Cross-Artifact Consistency

Validate relationships such as:

- `wrapper.result.json.artifacts.*` paths exist
- `plan.packet.json.spec_path` matches produced `spec.md`
- `plan.packet.json.rationale_path` matches produced `rationale.md`
- `plan.packet.json.goal_tree_path` matches produced `goal-tree.json`
- `goal-tree.json.metadata.profile` matches `plan.packet.json.profile`
- `wrapper.result.json.resolved_profile` matches `plan.packet.json.profile`

### 4. Contract Placement Rules

Catch fields that are valid somewhere but appear in the wrong place.

Examples:

- `ready_for_consumer` belongs in `plan.packet.json`, not in `goal-tree.json`
- wrapper result should summarize artifact locations, not redefine packet contents
- `goal-tree.json` should not carry packet-only readiness booleans

### 5. Content-Level Sanity Checks

These are not full semantic proofs, but high-value guardrails.

Examples:

- every `leaf_task` id in `plan.packet.json` should appear as an `executable_leaf` or stronger task node in `goal-tree.json`
- every task node in `goal-tree.json` should include:
  - `done_criteria`
  - `file_scope`
  - `verification`
  - `risk_level`
- `wrapper.result.json.status == completed` should not coexist with non-empty blockers unless explicitly allowed

## Input Contract

The validator should accept either:

### Option A: Run Directory

Example:

```text
docs/sejong/examples/greenfield-full-flow/
```

### Option B: Wrapper Result Path

Example:

```text
docs/sejong/examples/greenfield-full-flow/wrapper.result.json
```

The validator can derive the bundle directory from the wrapper result location.

## Output Contract

The validator should produce one machine-readable report plus one human-readable summary.

### Machine-Readable Result

Suggested file:

- `bundle-validation.result.json`

Suggested shape:

- `bundle_path`
- `status`
  - `pass | fail`
- `resolved_mode`
- `resolved_profile`
- `checks`
  - list of named check results
- `errors`
  - hard failures
- `warnings`
  - non-fatal concerns

### Human-Readable Summary

Suggested file:

- `bundle-validation.md`

Keep it short:

- status
- failed checks
- warnings
- recommended fixes

## Error Taxonomy

Use stable error codes so future automation can reason about failures.

### Presence Errors

- `missing_required_artifact`
- `unexpected_artifact_for_mode`

### Schema Errors

- `schema_invalid_wrapper`
- `schema_invalid_packet`
- `schema_invalid_goal_tree`

### Reference Errors

- `artifact_path_missing`
- `bundle_path_mismatch`
- `profile_mismatch`
- `mode_mismatch`

### Placement Errors

- `field_in_wrong_artifact`
- `packet_field_in_goal_tree`
- `goal_tree_field_in_packet`

### Sanity Errors

- `leaf_missing_goal_tree_node`
- `task_node_missing_execution_fields`
- `completed_status_with_blockers`

## Minimum v0.2 Scope

The first implementation should not try to prove everything.

It should definitely catch:

1. schema-invalid files
2. missing required files by mode
3. artifact path mismatches
4. profile mismatches
5. packet/goal-tree field placement drift

That alone catches the most common contract drift before a bundle reaches an executor.

## Recommended Implementation Shape

Start simple.

### Phase 1

- one script
- directory input
- JSON report to stdout
- non-zero exit on failure

### Phase 2

- write result files into the run directory
- add warning severity
- support validating many run folders in one invocation

### Phase 3

- integrate into release or CI checks
- summarize deterministic validator results for maintainers

## Suggested CLI Shape

Examples:

```bash
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow/
```

or

```bash
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow/wrapper.result.json
```

Possible flags:

- `--json`
- `--write-report`
- `--strict`

## Why This Should Exist Before Other v0.2 Work

Without a bundle validator:

- schema drift is caught too late
- improvements to Uigwe are harder to trust

With a bundle validator:

- the bundle contract becomes enforceable
- future wrapper and consumer work can depend on a stricter planning surface

## Related Tooling

- `scripts/project_summary.py`

## Success Criteria

The validator is successful when:

- it catches field-placement drift automatically
- it can validate the included public example bundles
- it provides stable error codes that future tooling can consume
- it reduces manual review work during package maintenance
