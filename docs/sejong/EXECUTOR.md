# Uigwe Executor Model

**Status:** Draft

## Purpose

The Uigwe executor model defines what happens **after planning**.

Its role is to take a validated Uigwe planning bundle and hand it to an execution harness without reopening planning by default.

## Why This Layer Exists

Uigwe already produces strong planning artifacts:

- `spec.md`
- `rationale.md`
- `plan.packet.json`
- `goal-tree.json`

But execution still needs a higher-level contract:

- what is the source of truth?
- who executes?
- when is replanning allowed?
- how does execution report back?

That is the job of the executor layer.

## Layering

The execution architecture is:

```text
Uigwe planner
-> bundle validator
-> executor layer
-> execution backend
-> execution feedback
-> optional Uigwe re-entry
```

Executor changes should be validated against the schema, example handoffs, and at least one representative Uigwe bundle, not only by anecdotal inspection.

## Terminology

### Executor

An **executor** is the post-planning handoff layer.

It is responsible for:

- accepting a validated Uigwe bundle
- choosing or representing an execution backend
- preserving the planning bundle as the source of truth
- returning execution feedback and re-entry signals
- owning execution-side metadata such as attempt identity, result persistence, and handoff retention semantics

### Consumer

The existing **consumer** concept remains useful, but it is narrower.

It focuses on:

- leaf-level execution behavior
- dispatch policy
- critic/verifier policy
- machine-readable execution feedback

In other words:

- `executor` is the higher-level orchestration handoff
- `consumer` is the lower-level execution contract

## Recommended Model

Use:

- **executor layer** as the formal post-planning handoff
- **Codex consumer** as a lower-level direct execution contract
- **Seungjeongwon** as the native execution implementation for substantial work
- **RalphExecutor** as an optional compatibility handoff for Ralph-capable hosts

In this model:

- `Uigwe` owns planning truth
- the `executor` owns execution truth and persistence rules
- Seungjeongwon owns implementation and verification behavior inside Codex

When the work is "improve Uigwe's executor contract itself," success should be defined by contract validation and a representative handoff exercise, not by local taste.

## Current Default

The recommended default executor for Uigwe is:

- `Seungjeongwon`

The canonical native backend is:

- the included repo-local `seungjeongwon` skill

Ralph-compatible handoff remains available, but it is no longer required for King Sejong execution.

Current implementation draft:

- `.agents/skills/seungjeongwon/SKILL.md`
  - executes approved scopes or validated Uigwe bundles directly in Codex
- `scripts/prepare_ralph_executor.py`
  - emits a machine-readable request plus a ready-to-run Ralph-compatible handoff prompt when that path is useful

## Executor Variants

Planned or implied variants:

- `Seungjeongwon`
- `RalphExecutor`
- `DirectExecutor`
- `TeamExecutor`

### `Seungjeongwon`

Best for:

- default King Sejong execution
- approved Uigwe bundles
- direct Codex implementation and verification
- evidence capture and re-entry advice

### `RalphExecutor`

Best for:

- ambiguous or substantial execution
- long-running work
- persistence and verification
- iterative completion pressure
- compatibility with existing Ralph-capable environments

### `DirectExecutor`

Best for:

- small, clear, low-risk leaf sets
- direct execution without the heavier Ralph loop

### `TeamExecutor`

Best for:

- coordination-heavy or strongly parallel work
- explicit staged multi-agent execution

## Source Of Truth Rule

For all executors, the Uigwe planning bundle is authoritative.

Minimum source-of-truth set:

- `plan.packet.json`
- `goal-tree.json`
- `spec.md`
- `rationale.md`

Optional but useful:

- `planning-summary.md`

Executors must not silently replace planning with fresh planning.

## Replanning Rule

Executors should not reopen planning unless execution discovers a real contradiction.

These re-entry target ids are machine-readable Uigwe escalation values, not protocol stage ids or separate required skills.
`brainstorming` maps directly to the `Design Exploration` stage.
`deep_interview` is the machine-readable re-entry target for `Intent Clarification` (`deep-interview`).

Allowed escalation targets:

- `local_reexploration`
- `brainstorming`
- `deep_interview`
- `human_review`

## Recommended Next Read

After this file:

1. `SEUNGJEONGWON_EXECUTOR.md`
2. `CODEX_CONSUMER.md`
3. `RALPH_EXECUTOR.md` when Ralph-compatible handoff is needed
