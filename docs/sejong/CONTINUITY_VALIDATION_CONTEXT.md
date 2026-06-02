# Continuity Capsule Validation Context

**Status:** Background context for commit and verification

## Purpose

This document records the background for the continuity-capsule change set so a
separate worktree can commit and validate it without depending on the original
chat session.

The problem being solved is long-session degradation after compaction. Research,
discussion, planning, execution state, rejected options, and verification status
can be compacted away, so a later model turn may continue with a weaker or stale
working set.

The selected design is a compact AI-facing continuity capsule. It is a bounded
index over runtime artifacts, not a human handoff note, not a raw memory replay,
not a Uigwe packet, and not an authority layer.

## What Changed

The change adds a new continuity-capsule contract and wires it into the existing
King Sejong runtime surfaces.

New contract and examples:

- `docs/sejong/CONTINUITY.md`
- `docs/sejong/continuity-capsule.schema.json`
- `docs/sejong/examples/continuity-capsule.example.json`
- `docs/sejong/examples/continuity-context.example.json`

New helper and replay validation:

- `docs/sejong/scripts/continuity_capsule.py`
- `docs/sejong/scripts/continuity_replay_gate.py`
- `docs/sejong/scripts/test_continuity_capsule.py`
- `docs/sejong/scripts/test_continuity_replay_gate.py`

Hook/runtime integration:

- `docs/sejong/scripts/king_sejong_hooks.py` now loads continuity capsule refs
  from active-context `artifact_refs`, injects compact projections into hook
  context, and blocks `PreCompact` / `Stop` when referenced capsules are broken
  or invalid.
- `docs/sejong/scripts/sejong_context.py` now supports `task_class` and
  `projection_profile` fields.
- `docs/sejong/king-sejong-context.schema.json` accepts those fields.

Validation and docs integration:

- `docs/sejong/scripts/validate_json_contracts.py` maps
  `sejong.continuity-capsule/v0.1-draft`.
- `docs/sejong/scripts/sejong_integrated_quality_gate.py` includes a continuity
  replay check.
- `docs/sejong/scripts/benchmark_instruction_surface.py` checks continuity
  strings in the instruction surface.
- `AGENTS.md`, `docs/sejong/ARTIFACT_STORAGE.md`, `docs/sejong/HOOKS.md`,
  `docs/sejong/PROTOCOL.md`, `docs/sejong/README.md`,
  `docs/sejong/RUNTIME_CONTRACT.md`, `docs/sejong/SUMMARY_PROJECTION.md`, and
  `docs/sejong/VALIDATION.md` were updated to reference the new contract.

## Behavior To Verify

Validate these claims in the separate worktree:

- A valid continuity capsule passes schema and helper validation.
- Hook context includes `continuity_capsule=...` projection when active context
  references a valid capsule.
- `PreCompact` blocks broken or invalid continuity capsule refs.
- `Stop` blocks broken or invalid continuity capsule refs.
- Projection is compact and profile-aware; it should not replay raw traces.
- `record-decision` and `record-rejection` update structured capsule records
  without manual JSON editing.
- The replay gate proves `PreCompact` allows a valid continuity state and
  `PostCompact` injects the required working-set projection.
- The installed user-scope docs layout can run the same replay gate. This is
  important because installed docs live under `skills/sejong/docs/`, not
  `docs/sejong/`.

## Critical Non-Goals

Do not validate this as a general memory system.

Do not let the capsule approve gates, redefine success, replace Uigwe packets,
replace Seungjeongwon verification, or complete work from stale verification.

Do not inject raw Sillok traces, raw logs, or full debate transcripts into every
prompt. The capsule should project only the compact working-set index and refs.

Do not generalize this to "all long sessions are solved." The promoted behavior
is the continuity artifact and replay gate for compact working-set preservation.
Task-class outcome improvement still requires outcome-quality evidence.

## Recommended Verification Commands

Run these from the repo root in the separate worktree:

```bash
python3 docs/sejong/scripts/test_continuity_capsule.py
python3 docs/sejong/scripts/test_continuity_replay_gate.py
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_context.py
python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py'
python3 -m compileall -q docs/sejong/scripts
```

Run JSON contract validation with the dependency wrapper used by this repo
family:

```bash
uv run --with jsonschema --with referencing python docs/sejong/scripts/validate_json_contracts.py
```

Run the deterministic guardrails:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/benchmark_sejong_surface.py --write --require-targets
python3 docs/sejong/scripts/sejong_integrated_quality_gate.py --work-dir "$(mktemp -d)"
```

Run the direct replay gate:

```bash
python3 docs/sejong/scripts/continuity_replay_gate.py judge \
  --context docs/sejong/examples/continuity-context.example.json \
  --require "continuity_capsule=capsule-continuity-example" \
  --require "continuity_rejected=Use only markdown handoff" \
  --forbid "Replay full trace history" \
  --max-chars 2500
```

Run install verification after committing or before publishing:

```bash
bash scripts/install-sejong.sh --scope user --force
bash scripts/install-sejong.sh --scope user --verify
```

Then verify the installed docs surface directly:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/sejong"
python3 docs/scripts/continuity_replay_gate.py judge \
  --context docs/examples/continuity-context.example.json \
  --repo-root . \
  --require "continuity_capsule=capsule-continuity-example" \
  --require "continuity_rejected=Use only markdown handoff" \
  --forbid "Replay full trace history" \
  --max-chars 2500
python3 docs/scripts/test_continuity_replay_gate.py
```

## Expected Passing Signals

Expected source-repo results from the original implementation pass:

- `test_continuity_capsule.py`: 5 tests OK
- `test_continuity_replay_gate.py`: 3 tests OK
- `test_king_sejong_hooks.py`: 37 tests OK
- `python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py'`:
  128 tests OK
- `validate_json_contracts.py`: `schemas=17 instances=52 skipped=12 failures=0`
- `benchmark_instruction_surface.py --write --require-targets`: 25/25 pass
- `benchmark_sejong_surface.py --write --require-targets`: 29/29 pass
- `sejong_integrated_quality_gate.py`: `passed=true`, including
  `continuity_replay_preserves_working_set_projection`
- installed replay gate: `passed=true`, projection under 2500 chars

The installer may print rsync warnings about non-empty installed docs
directories during `--force`. Treat those as non-blocking only if the installer
still reports `King Sejong user install verified` and the installed replay gate
passes. If install verification fails, investigate the rsync warning as a real
drift signal.

## Review Focus

Reviewers should inspect these risk points:

- `continuity_replay_gate.py` materializes context-local continuity capsule refs
  only for refs that look like continuity capsule JSON files. It should not hide
  broken refs for unrelated artifact types.
- Hook projection should skip invalid capsules for normal context injection but
  still expose invalid refs and block `PreCompact` / `Stop`.
- `projection_profile` from active context should override capsule profile when
  set, but unsupported profiles should fall back safely.
- Helper commands should preserve schema validity after updates.
- Example context should work from both source repo layout and installed
  `skills/sejong/docs/` layout.
- The continuity capsule must remain an artifact index and must not become a
  second Uigwe or Seungjeongwon authority surface.

## Commit Notes

A suitable commit should explain why the continuity artifact exists: preserving
compact AI working context across compaction without replaying raw history or
weakening Sejong authority boundaries.

Suggested trailers to include if using the Lore protocol:

```text
Constraint: Long sessions need compact working-set continuity without raw trace replay
Rejected: Use only markdown handoff | not hook-validated AI working state
Rejected: Replay full trace history | over-injects context and can expose private or untrusted evidence
Scope-risk: moderate
Directive: Do not let continuity capsules approve Uigwe gates or replace fresh verification
Tested: unittest discover, JSON contract validation, instruction benchmark, Sejong benchmark, integrated quality gate, user-scope install verify, installed replay gate
```
