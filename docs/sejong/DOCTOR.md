# King Sejong Doctor

**Status:** Read-only health check

## Purpose

`sejong_doctor.py` is the local health check for King Sejong source and runtime
surfaces. It reports problems; it does not repair, update, install, uninstall,
or mutate Codex config.

Use it when install verification fails, hooks behave unexpectedly, schema
validation cannot run, a Context or session binding looks unhealthy, or a user wants a quick
environment check before release work.

## Usage

From the source checkout:

```bash
bash docs/sejong/scripts/run_with_supported_python.sh docs/sejong/scripts/sejong_doctor.py
```

The launcher selects Python 3.11 or newer from `PATH`, then falls back to a
`uv`-managed interpreter. It does not replace the system Python. If neither is
available, it stops with an environment setup message before the doctor runs.

Machine-readable output:

```bash
bash docs/sejong/scripts/run_with_supported_python.sh docs/sejong/scripts/sejong_doctor.py --json
```

Check a specific durable Context explicitly:

```bash
bash docs/sejong/scripts/run_with_supported_python.sh docs/sejong/scripts/sejong_doctor.py --context ~/.codex/sejong/runs/<repo-id>/<run-id>/king-sejong-context.json
```

Without `--context`, the doctor does not treat `state/active-context.json` as a
foreground Context. It scans durable runs and runtime state only for diagnostics.

For tests or hermetic CI that should not depend on local Python packages:

```bash
bash docs/sejong/scripts/run_with_supported_python.sh docs/sejong/scripts/sejong_doctor.py --skip-python-deps --skip-active-context
```

## Checks

The doctor currently checks:

- managed source paths and source-only boundaries
- plugin adapter JSON readability
- Python modules required by JSON schema validation
- git dirty state
- explicitly selected durable Context shape and active Seungjeongwon run HUD
- `multisession-active-runs`: warns when Sejong runtime run contexts still
  have active continuations, so cleanup and completion claims can account for
  live work.
- `active-pointer-staleness`: audits the preserved legacy pointer for migration
  and cleanup diagnostics only. Its freshness never grants hook injection
  authority and a newer matching run is never auto-selected.
- `runtime-broken-refs`: fails for broken or invalid ambiguity-register,
  Seungjeongwon-run, or continuity-capsule refs that apply to the checked repo;
  off-repo broken refs are reported as warnings.
- `runtime-locks`: reports runtime lock health, including malformed lock
  metadata as failures and stale owner-process locks as warnings with owner
  session, run, device, operation, and reason metadata.
- `runtime-cleanup-dry-run`: reports which active runtime runs would be
  retained by cleanup without deleting or repairing runtime state.
- `install-update-drift`: runs user-scope install verification only from the
  trusted King Sejong source checkout and warns when the user-scope install is
  stale or cannot be inspected.

Missing `jsonschema` or `referencing` is reported as a failure because
`validate_json_contracts.py` cannot run without them. A local one-shot command
is:

```bash
uv run --with jsonschema --with referencing python3 docs/sejong/scripts/validate_json_contracts.py
```

## Exit Status

Exit code `0` means no failing checks. Warnings may still appear for expected
runtime state such as a preserved legacy pointer or a dirty source checkout.

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
