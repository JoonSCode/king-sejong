# King Sejong Continuity Capsule

**Status:** Draft

## Purpose

Long King Sejong sessions can lose quality when compaction removes the research,
discussion, planning, or execution working set that the next model turn needs.

The continuity capsule is the compact AI-facing index for that working set. It is
not a human handoff note, not raw memory, not a new planning packet, and not an
authority layer.

The capsule follows [continuity-capsule.schema.json](continuity-capsule.schema.json)
and is stored as:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/<repo-id>/<run-id>/continuity-capsule.json
```

The active context references it through `artifact_refs`.

## Contract

A continuity capsule records only the state needed to rebuild the next useful AI
working set:

- objective and task class
- current court surface and route sequence
- pending gates
- selected decisions and rejected options
- active blockers
- verification state
- next action
- stale-state triggers
- source artifact refs and evidence refs

It must store refs to Sillok traces, ambiguity registers, Uigwe packets,
Seungjeongwon run artifacts, route decisions, or other runtime artifacts instead
of copying raw logs or private evidence.

## Projection Profiles

Hooks inject a projection derived from the capsule, never the full capsule by
default.

Profiles:

- `micro`: objective, current surface, pending gates, blockers, next action, and
  critical refs
- `standard`: `micro` plus the selected decision, verification status, and source
  artifact summary
- `frontier`: `standard` plus rejected option summary, stale triggers, and
  `do_not_do` guardrails
- `retrieval`: refs-first projection for turns where the model should inspect
  artifacts or files before deciding

The projection profile may be stored on the active context as `projection_profile`
or on the capsule as `projection_profile`. Hook output should stay compact and
model-visible; raw traces remain retrieval material.

## Stale-State Rules

A capsule must not be applied silently when the repo, objective, task class,
artifact refs, or evidence basis no longer match the current work.

Continuation should refresh or reject the capsule when:

- `repo_root` does not cover the current workspace
- `objective` or `task_class` changes
- a source artifact ref is missing, unreadable, or invalid
- a write-like action depends on stale verification
- privacy or security risk flags require fresh review
- the user explicitly exits Sejong or switches to another workflow

Completion still requires fresh verification. A capsule may remind the model what
was last verified, but it cannot make stale verification current.

## Hook Behavior

When the active context references a valid continuity capsule:

- `UserPromptSubmit`, `SessionStart`, and `PostCompact` inject the compact
  projection.
- `PreCompact` blocks compaction when a continuity capsule reference is broken or invalid.
- `Stop` blocks completion when a referenced capsule is broken or invalid.

Hooks are guardrails. They do not approve Uigwe gates, change Seungjeongwon
status, redefine success, or decide final synthesis from the capsule.

## Helper

The reference helper validates and projects capsules:

```bash
python3 docs/sejong/scripts/continuity_capsule.py check --path <continuity-capsule.json>
python3 docs/sejong/scripts/continuity_capsule.py update --path <continuity-capsule.json> --next-action "Run focused verification." --evidence-ref test-output
python3 docs/sejong/scripts/continuity_capsule.py record-decision --path <continuity-capsule.json> --decision-id capsule-as-index --summary "Use capsule as compact artifact index." --why "It preserves working state without raw replay." --ref docs/sejong/CONTINUITY.md
python3 docs/sejong/scripts/continuity_capsule.py record-rejection --path <continuity-capsule.json> --option-id handoff-only --summary "Use only markdown handoff." --reason "It is not hook-validated AI working state." --ref docs/sejong/ROUTER.md
python3 docs/sejong/scripts/continuity_capsule.py project --path <continuity-capsule.json> --profile standard
python3 docs/sejong/scripts/continuity_replay_gate.py judge --context <king-sejong-context.json> --require "continuity_capsule=" --max-chars 2500
```

Use `start` to create a minimal capsule when a long-running workflow first needs
compaction-safe continuity. Use `update` for routine route, blocker, reference,
next-action, and verification-state movement. Richer decision or rejection
records must be written with `record-decision` and `record-rejection` or through
equivalent structured artifact writes under the Sejong run directory when a
structured council or Uigwe decision changes.

Use `continuity_replay_gate.py` before claiming this continuity path improves a
long session. The replay gate checks that valid capsule refs can pass
`PreCompact`, that `PostCompact` injects the required working-set projection, and
that projection stays under the configured size budget.
