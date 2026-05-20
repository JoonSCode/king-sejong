# Uigwe RalphExecutor

**Status:** Draft

## Purpose

`RalphExecutor` is the default execution implementation for Uigwe.

It takes a validated Uigwe planning bundle and hands execution to the current Codex-native Ralph skill or any AI agent harness that can forward the generated Ralph prompt without reopening planning by default.

## Canonical Backend

The canonical Ralph backend is the Ralph skill provided by the host agent environment.

Other Ralph variants may exist as:

- legacy references
- workspace-local mirrors
- compatibility surfaces

but `RalphExecutor` should target the current Codex-native Ralph behavior.

## Why RalphExecutor

Ralph is the best default executor for Uigwe when:

- the work is substantial
- persistence matters
- completion verification matters
- a single-shot direct executor would be too weak

In short:

- `Uigwe` decides **what should be done**
- `RalphExecutor` ensures it is **carried through**

## Input Contract

`RalphExecutor` expects a validated bundle with:

- `plan.packet.json`
- `goal-tree.json`
- `spec.md`
- `rationale.md`

Optional:

- `planning-summary.md`

The handoff request schema is:

- `ralph-executor.schema.json`

Current implementation draft:

- `scripts/prepare_ralph_executor.py`

The generated handoff package is intentionally dual-purpose:

- `ralph-executor.request.json`
  - machine-readable request for an execution harness
- `ralph-next-step.md`
  - ready-to-run prompt that can be given directly to `ralph`

The request includes:

- bundle paths
- attempt identity plus bundle fingerprint
- resolved planning context
- executable leaf scope and recommended order
- `git_policy` for commit and worktree closeout behavior in v0.4 requests
- execution rules and output expectations
- a canonical next-step command plus user-facing `1` and `3` handoff options
- the ready-to-run handoff prompt text

Executor-contract changes should be evaluated with schema validation, example handoffs, and at least one representative bundle.

## Source Of Truth

`RalphExecutor` treats the Uigwe bundle as the source of truth.

That means:

- do not redo planning by default
- do not reinterpret the task from scratch
- do not silently widen scope
- do not treat Sejong aliases as new execution scope beyond the selected Uigwe plan

Instead, execute against:

- selected plan
- retained dependency structure
- executable leaves
- explicit verification requirements

If a Sejong-routed request reaches RalphExecutor, Sejong has already finished its routing job. Execution still starts from `plan.packet.json`, `goal-tree.json`, `spec.md`, `rationale.md`, and optional `planning-summary.md`; Ralph should not infer new work from the naming metaphor.

## Allowed Ralph Behavior

Ralph may:

- execute the leaves
- run verification
- iterate on failed execution
- escalate when contradictions appear

Ralph should not:

- replace Uigwe planning with fresh planning
- ignore the bundle and improvise new scope
- silently absorb design changes that should trigger re-entry

## Re-entry Contract

If Ralph execution discovers a contradiction:

The re-entry target names below are machine-readable Uigwe escalation values, not protocol stage ids or separate required skills.
`brainstorming` maps directly to `Design Exploration`.
`deep_interview` is the machine-readable re-entry target for `Intent Clarification` (`deep-interview`).

### Local problem

Examples:

- missing narrow file detail
- local dependency reshaping
- one leaf needs refinement

Action:

- return `local_reexploration`

### Design problem

Examples:

- selected approach no longer decomposes cleanly in execution
- retained alternative becomes clearly stronger

Action:

- return `brainstorming` (`Design Exploration`)

### Intent problem

Examples:

- core goal is misread
- non-goals are violated
- decision boundaries are invalid

Action:

- return `deep_interview` (`Intent Clarification`)

## Relationship To Codex Consumer

`RalphExecutor` sits above the leaf-level consumer contract.

Use this mental model:

- `RalphExecutor` = execution orchestrator
- `Codex consumer` = execution lane semantics and feedback shape

This means `RalphExecutor` should reuse:

- leaf contract expectations
- verifier expectations
- feedback concepts

without collapsing back into direct-consumer-only execution.

## Result Contract

The result should report:

- which attempt executed
- when it started and finished
- whether Ralph accepted the bundle
- whether execution is accepted, in progress, completed, blocked, invalidated, or failed
- where execution feedback lives for that attempt
- git evidence when the handoff enables commit-producing execution
- how the latest root-level handoff artifacts were retained
- which re-entry target is recommended, if any

For Uigwe self-improvement work, Ralph should not treat this contract as done until the executor-facing schemas, examples, and handoff generation still validate.

## Git Hygiene

Git hygiene is executor behavior, not Uigwe planning behavior.

`Uigwe` leaves remain execution contracts. They are not automatically one Git commit each.
`RalphExecutor` may group one or more dependency-ready leaves into a coherent commit group when the handoff's `git_policy` enables commits.

Supported `git_policy.mode` values:

- `no_commit`: execute and report changes without preparing commit evidence
- `prepare_only`: report the git policy outcome and proposed commit grouping, but do not create commits
- `create_commits`: create commits for coherent commit groups and require git evidence before reporting `completed`

Rules:

- do not create commits unless `git_policy.mode` is `create_commits`
- use commit groups, not one-commit-per-leaf as a blanket rule
- record preflight branch/head and existing dirty paths before editing when practical
- protect pre-existing unrelated dirty paths instead of sweeping them into a commit
- for `create_commits`, a `completed` result must include commit shas, affected leaf ids, and tracked worktree clean evidence
- v0.4 executor results must echo the handoff `git_policy`; legacy v0.3 results without `git_policy` are only compatibility artifacts
- clean finish means no unintended tracked changes in the target scope; it does not mean deleting ignored build caches, DerivedData, logs, or other evidence artifacts
- for submodule work, commit the child repo first and then close out the parent gitlink when the parent repo is in scope

Verification remains proportional to the changed scope.
Use incremental build and focused tests during the edit loop; reserve clean builds, full UI suites, archives, and destructive cleanup for release or CI-grade gates.

## Lifecycle Rules

Current default is intentionally simple:

- the planning bundle stays canonical at the bundle root
- `ralph-executor.request.json` and `ralph-next-step.md` at the bundle root represent the latest active handoff
- `ralph-executor.result.json` and `codex-consumer-feedback.json` at the bundle root are the durable persistence targets for the current attempt

If a new handoff is generated later:

- it creates a new `attempt_id` and `attempt_number`
- it may supersede the previous root-level handoff
- it should not delete result or feedback artifacts from earlier execution without an explicit archive policy

For now, `RalphExecutor` stays flat at the bundle root instead of introducing an `execution/manifest.json` or attempt directories.
That heavier model remains a future option if Uigwe needs multi-attempt history as a first-class capability.

## Current Handoff Flow

Recommended sequence:

1. finish Uigwe planning
2. validate the bundle
3. optionally generate `planning-summary.md`
4. run `prepare_ralph_executor.py`
5. hand `ralph-executor.request.json` to an execution harness or pass `ralph-next-step.md` directly to the Ralph-backed agent surface

Example:

```bash
python3 docs/sejong/scripts/prepare_ralph_executor.py docs/sejong/examples/brownfield-decompose-only --write
```

This writes:

- `ralph-executor.request.json`
- `ralph-next-step.md`

If you do not use `--json`, the script prints the ready-to-run Ralph prompt to stdout.

Recommended user-facing next step after handoff preparation:

- `1. Run now here` -> continue immediately in the current session without making the user type a command
- `3. Run in another session or terminal` -> `$ralph follow <bundle_dir>/ralph-next-step.md`

Mirror the generated numbering exactly when presenting these options again. Do not renumber the handoff surface locally.

## Contract-Gated Improvement Loop

When the task is to improve Uigwe's executor contract itself:

1. patch the executor-facing docs, schema, examples, or generator
2. run:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/prepare_ralph_executor.py docs/sejong/examples/brownfield-decompose-only --write
```

3. inspect generated handoff artifacts if the command fails
4. keep patching until the contract validates or a real blocker remains

This keeps Ralph in its normal completion loop while making the stop condition explicit and machine-checkable.

## Preferred Use

Default recommendation:

- small and obvious work -> consider `DirectExecutor`
- substantial or ambiguous execution -> `RalphExecutor`
- coordination-heavy work -> `TeamExecutor`

For Uigwe's current maturity, `RalphExecutor` is the safest default.
