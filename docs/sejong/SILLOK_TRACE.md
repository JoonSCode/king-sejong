# Sillok Trace

**Status:** Draft

## Purpose

`Sillok` records compact King Sejong evidence without turning runtime logs into
tracked repository files.

Use it for route decisions, tool evidence, verification results, handoffs,
blockers, and security reviews that should survive a session handoff.

## Storage

Sillok trace files are external runtime artifacts by default:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/<repo-id>/<run-id>/sillok-record.jsonl
```

Do not promote a raw trace into the repository unless the user explicitly asks
for a commit-ready Sillok record.

## Event Contract

Each JSONL line follows [sillok-trace-event.schema.json](sillok-trace-event.schema.json).

Required fields include:

- `event_id`
- `run_id`
- `active_context_id`
- `surface`
- `event_kind`
- `summary`
- `refs`
- `risk_flags`
- `human_approval_ref`

Use `refs` for file paths, command evidence, source links, scorecards, or
runtime artifacts. Keep `summary` compact and avoid copying secrets or raw
private data into traces.

## Helper

The reference helper records and checks trace events:

```bash
python3 docs/sejong/scripts/sillok_trace.py append \
  --repo-id king-sejong \
  --run-id example \
  --active-context-id ctx-example \
  --surface jangyeongsil \
  --event-kind security_review \
  --summary "External source treated as untrusted evidence." \
  --risk-flag untrusted_content \
  --ref docs/sejong/SECURITY.md

python3 docs/sejong/scripts/sillok_trace.py check \
  "${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/king-sejong/example/sillok-record.jsonl"
```

## Security Gate

`sillok_trace.py check` fails when one event combines all of:

- `private_data`
- `untrusted_content`
- `external_action`

unless `human_approval_ref` is present.

This is a trace-level guardrail. It does not replace Codex permissions, user
review, hook checks, or Seungjeongwon verification.
