# King Sejong Doctor

**Status:** Read-only health check

## Purpose

`sejong_doctor.py` is the local health check for King Sejong source and runtime
surfaces. It reports problems; it does not repair, update, install, uninstall,
or mutate Codex config.

Use it when install verification fails, hooks behave unexpectedly, schema
validation cannot run, active context looks stale, or a user wants a quick
environment check before release work.

## Usage

From the source checkout:

```bash
python3 docs/sejong/scripts/sejong_doctor.py
```

Machine-readable output:

```bash
python3 docs/sejong/scripts/sejong_doctor.py --json
```

Check a specific active context:

```bash
python3 docs/sejong/scripts/sejong_doctor.py --context ~/.codex/sejong/state/active-context.json
```

For tests or hermetic CI that should not depend on local Python packages:

```bash
python3 docs/sejong/scripts/sejong_doctor.py --skip-python-deps --skip-active-context
```

## Checks

The doctor currently checks:

- managed source paths and source-only boundaries
- plugin adapter JSON readability
- Python modules required by JSON schema validation
- git dirty state
- active context shape and active Seungjeongwon run HUD

Missing `jsonschema` or `referencing` is reported as a failure because
`validate_json_contracts.py` cannot run without them. A local one-shot command
is:

```bash
uv run --with jsonschema --with referencing python3 docs/sejong/scripts/validate_json_contracts.py
```

## Exit Status

Exit code `0` means no failing checks. Warnings may still appear for expected
runtime state such as no active context or a dirty source checkout.

Exit code `1` means at least one failing check needs action before claiming the
environment is healthy.

## Non-Goals

The doctor must not:

- edit `${CODEX_HOME:-~/.codex}/config.toml`
- install or uninstall skills
- fast-forward the source checkout
- repair active context
- write runtime artifacts
- decide that a Seungjeongwon run is complete
