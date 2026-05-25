# Seungjeongwon Executor

**Status:** Draft

## Purpose

`Seungjeongwon` / `승정원` is King Sejong's native executor.

It exists so `/sejong` can be a real all-in-one work surface:

```text
research -> decision -> Uigwe planning -> Seungjeongwon execution -> verification -> evidence
```

Seungjeongwon accepts either:

- a validated Uigwe bundle
- a clear Sejong direct scope

Then it carries the work through implementation, verification, and feedback.

## Relationship To Uigwe

Uigwe owns planning truth.

Seungjeongwon owns execution truth.

When a Uigwe bundle exists, Seungjeongwon treats these files as authoritative:

- `plan.packet.json`
- `goal-tree.json`
- `spec.md`
- `rationale.md`
- optional `planning-summary.md`

It does not reopen planning unless execution discovers a contradiction.

Uigwe owns the approved goal, non-goals, success criteria, verification bar, must-preserve behaviors, and re-entry triggers. Seungjeongwon may adapt decomposition and implementation tactics when the original execution hypothesis is wrong, but it must preserve those guardrails unless the user or Uigwe explicitly reopens them.

Uigwe handoff leaves are not final implementation todos. They are bounded objectives that are safe to start from. Seungjeongwon owns the executor-side loop that turns each handoff leaf into actionable leaves before execution begins.

## Execution Default

The native default is:

- execute in Codex through Seungjeongwon
- verify in Codex
- report execution feedback directly

## Execution Inputs

For a Uigwe bundle:

- bundle directory or `wrapper.result.json`
- selected handoff leaf ids, or all handoff leaves by default
- optional git policy from the user or repo rules

For direct action:

- explicit user request
- target files or repo scope when relevant
- done criteria
- verification command or observable proof when known

## Execution Rules

1. Read the source of truth before editing.
2. Identify dependency-ready handoff leaves or direct scope.
3. Run executor-side todo decomposition until the selected work is represented as actionable leaves.
4. Execute only actionable leaves derived from the approved handoff leaves or explicit direct scope.
5. Preserve planning and execution boundaries:
   - planning uncertainty -> return to Uigwe
   - implementation failure -> debug and continue
   - blocked external decision -> ask the user
6. Verify each completed actionable leaf or direct task.
7. Record evidence before reporting completion.

## Actionable Decomposition Loop

Before implementation, Seungjeongwon decomposes each selected handoff leaf into actionable work:

```text
todo listup
-> todo verification
-> subtodo decomposition
-> repeat until actionable leaves exist
-> execution loop
```

The `todo listup -> todo verification -> subtodo decomposition` loop repeats until every selected todo is either:

- an `actionable_leaf`
- blocked with explicit blocker evidence
- invalidated with a recommended Uigwe re-entry target

An actionable leaf must have:

- a concrete task
- a clear first edit, command, or inspection target
- observable done criteria
- file or responsibility scope that is narrow enough to execute safely
- dependency prerequisites that are satisfied or explicitly blocked
- a verification method that can produce fresh proof
- a failure path that supports a next hypothesis or escalation

Seungjeongwon may split, merge, reorder, or locally reshape todos while preserving the Uigwe contract. It must not broaden scope, weaken the verification bar, remove must-preserve behavior, or redefine success to make a todo pass.

If the 4-6 loop keeps failing because the todo is too broad, dependency order is wrong, or the first implementation hypothesis was weak, Seungjeongwon continues local decomposition. If the handoff leaf itself is wrong, it recommends Uigwe `local_reexploration`. If the chosen design is wrong, it recommends `brainstorming`. If the goal, non-goals, success criteria, or must-preserve behavior are incomplete or contradicted, it recommends `deep_interview` or `human_review`.

## Visible Execution Board

When Codex todo tooling is available, Seungjeongwon uses it as the user-visible execution board.

Before implementation begins, publish the initial actionable leaf list through Codex todo/update_plan. The visible board should show the current handoff leaf, actionable todos, dependency order, and verification-oriented work. It is not a private scratchpad and should not hide material execution reshaping from the user.

Seungjeongwon must not silently overwrite an existing visible todo when execution changes the shape of the work. If scope, dependency order, done criteria, or verification method changes, append a redefinition event todo such as `R1: redefine execution todo after failed activation proof`, mark the old todo as replaced or invalidated in the visible text when the tooling has only basic statuses, and add the replacement todo as a new item.

Use the execution attempt ledger, not new visible todos, for small implementation hypotheses that stay inside the same actionable todo. A visible redefinition event is required when the actionable todo itself changes. Uigwe re-entry is required when the approved goal, non-goals, success criteria, must-preserve behavior, verification bar, or other guardrails become unstable.

When execution feedback is persisted or handed back as JSON, record the same user-visible board movement in `visible_todo_events`. This ordered event list should include initial publication, starts, verification results, redefinitions, replacements, completions, blocks, or `board_unavailable` when the host lacks todo tooling. A typical visible reshaping sequence is `T2` published, `T2` verification fails, `R1` records the redefinition, `T2` is marked replaced, and replacement todos `T2a` and `T2b` are added before execution continues.

## Execution Attempt Loop

After actionable leaves exist, Seungjeongwon runs:

```text
hypothesis
-> implementation or tool action
-> verification
-> evidence record
-> retry or escalation
```

The loop continues until the actionable leaf is completed, blocked, invalidated, or escalated. A failed verification result is not itself a reason to change the success criteria; it is evidence for the next hypothesis unless it proves that Uigwe re-entry is required.

Each attempt should record:

- `attempt_id`
- source handoff leaf id
- actionable leaf id
- hypothesis
- action taken
- verification command or observable proof
- result
- finding
- next decision
- evidence refs

The executor should write this ledger into external Sejong runtime artifacts by default, usually alongside `execution-feedback.json` or `sillok-record.jsonl`.

## Execution Feedback And Re-entry

Seungjeongwon treats execution as a way to test planning assumptions.

- If only implementation details differ from the plan, adjust tactics locally, verify, and report the deviation.
- If actionable decomposition cannot produce stable actionable leaves because the handoff leaf's scope, dependency, or verification method is wrong, perform local re-exploration or recommend Uigwe `local_reexploration`.
- If an architecture or design assumption fails during decomposition or execution, stop widening execution and recommend Uigwe `brainstorming`.
- If the goal, non-goals, success criteria, or must-preserve behavior are incomplete or contradicted, ask for `human_review` or Uigwe `deep_interview`.

The executor must not silently redefine success to make verification pass.

## Artifact Storage

Execution evidence follows [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md).

By default, Seungjeongwon stores execution feedback, verification notes, and evidence snapshots outside the target repository under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`. It should not create git-tracked evidence or planning files unless the user explicitly asks to promote or commit them.

Implementation edits requested by the user still happen in the target workspace. This storage rule applies to Sejong-generated research, planning, runtime, and evidence artifacts, not to the source files the user asked Seungjeongwon to change.

## Output Contract

Seungjeongwon reports:

- `status`: `completed`, `blocked`, `invalidated`, or `failed`
- completed leaf ids or Sejong direct scope
- blocked or invalidated scope with reason
- files changed or artifacts produced
- actionable decomposition evidence
- visible todo board updates, including replacement or redefinition events when they occurred
- `visible_todo_events` when machine-readable execution feedback is produced
- execution attempt ledger summary
- verification evidence
- recommended Uigwe re-entry target:
  - `none`
  - `local_reexploration`
  - `brainstorming`
  - `deep_interview`
  - `human_review`
- git evidence when commits are requested or produced

## Evidence Rules

Completion requires fresh proof.

Acceptable evidence includes:

- tests, typecheck, lint, build, or schema validation output
- bundle validation output
- manual runtime check with clear observed result
- git status and commit evidence when closeout is requested
- explicit blocker evidence when completion is not possible
