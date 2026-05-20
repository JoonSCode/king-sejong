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
- a clear direct-action scope selected by Sejong

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

## Relationship To Ralph

Ralph is no longer required for King Sejong to execute work.

Ralph-compatible artifacts remain useful when:

- the workspace already has a separate Ralph loop installed
- the user wants execution to continue in another session
- a long-running task benefits from a separate persistent completion loop

In that case, Seungjeongwon may prepare or consume Ralph-compatible handoff artifacts through `RALPH_EXECUTOR.md`.

But the native default is:

- execute in Codex through Seungjeongwon
- verify in Codex
- report execution feedback directly

## Execution Inputs

For a Uigwe bundle:

- bundle directory or `wrapper.result.json`
- selected leaf ids, or all executable leaves by default
- optional git policy from the user or repo rules

For direct action:

- explicit user request
- target files or repo scope when relevant
- done criteria
- verification command or observable proof when known

## Execution Rules

1. Read the source of truth before editing.
2. Identify dependency-ready work.
3. Execute only the approved leaves or explicit scope.
4. Use parallel execution only when file scopes do not conflict.
5. Keep planning and execution separate:
   - planning uncertainty -> return to Uigwe
   - implementation failure -> debug and continue
   - blocked external decision -> ask the user
6. Verify each completed leaf or direct task.
7. Record evidence before reporting completion.

## Output Contract

Seungjeongwon reports:

- `status`: `completed`, `blocked`, `invalidated`, or `failed`
- completed leaf ids or direct-action scope
- blocked or invalidated scope with reason
- files changed or artifacts produced
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

## When To Use Ralph-Compatible Handoff

Use Ralph-compatible handoff only when it adds value:

- the user wants work to continue outside the current session
- the task is long-running and needs a separate persistent loop
- an existing environment already provides `$ralph`
- compatibility with earlier RalphExecutor artifacts matters

Otherwise, execute natively through Seungjeongwon.
