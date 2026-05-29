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
- decomposing Uigwe handoff leaves into actionable leaves before execution when needed
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
- **TeamExecutor** as an optional backend for `$team` wrappers when bounded worker parallelism is worth the coordination cost

In this model:

- `Uigwe` owns planning truth
- the `executor` owns execution truth and persistence rules
- Seungjeongwon owns todo listup, todo verification, subtodo decomposition, implementation, verification, and attempt-ledger behavior inside Codex
- TeamExecutor owns worker process coordination, mailbox state, and leases only when explicitly selected

When the work is "improve Uigwe's executor contract itself," success should be defined by contract validation and a representative handoff exercise, not by local taste.

## Current Default

The recommended default executor for Uigwe is:

- `Seungjeongwon`

The canonical native backend is:

- the included repo-local `seungjeongwon` skill

Current implementation draft:

- `.agents/skills/seungjeongwon/SKILL.md`
  - executes approved scopes or validated Uigwe bundles directly in Codex

## Executor Variants

Planned or implied variants:

- `Seungjeongwon`
- `DirectExecutor`
- `TeamExecutor`

### `Seungjeongwon`

Best for:

- default King Sejong execution
- approved Uigwe bundles
- direct Codex implementation and verification
- evidence capture and re-entry advice

### `DirectExecutor`

Best for:

- small, clear, low-risk actionable leaf sets
- direct execution without a heavier execution loop

### `TeamExecutor`

Best for:

- coordination-heavy or strongly parallel work
- explicit staged multi-agent execution
- `$team` wrappers that launch separate Codex CLI or explicitly configured compatible workers in `tmux` panes

`TeamExecutor` is optional. It is not the default executor, and it should not replace Seungjeongwon for ordinary execution.

The safe coordination shape is mailbox-lite:

- one lead-owned source of truth
- Sejong-owned state under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/`
- append-only mailbox messages for claims, objections, questions, responses, evidence references, risks, blockers, status, and verification
- optional progress pipes for ephemeral tmux status only
- lead-opened and lead-closed rounds
- file leases before any worker writes
- no worker vote, consensus, or direct gate approval

For Jiphyeonjeon, `TeamExecutor` may run a mailbox-mediated chamber: independent first-round briefs followed by a bounded cross-challenge round where workers answer each other's strongest objections by message id. The lead Sejong agent still owns synthesis, rejected options, confidence, next surface, and final verification.

For Seungjeongwon execution, `TeamExecutor` may dispatch disjoint implementation, critic, or verifier workers only when dependencies and file scopes are non-overlapping. If file scope is unclear, use `Seungjeongwon` or `DirectExecutor` instead.

See [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) for the `$team` state, mailbox, tmux worker, and lease contract.

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
