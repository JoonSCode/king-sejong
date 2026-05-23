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

Uigwe owns the approved goal, non-goals, success criteria, verification bar, must-preserve behaviors, and re-entry triggers. Seungjeongwon may adapt implementation tactics when the original execution hypothesis is wrong, but it must preserve those guardrails unless the user or Uigwe explicitly reopens them.

## Execution Default

The native default is:

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
4. Use parallel execution only when file scopes do not conflict. `$team` workers require Sejong-owned state, mailbox evidence, and file leases.
5. Keep planning and execution separate:
   - planning uncertainty -> return to Uigwe
   - implementation failure -> debug and continue
   - blocked external decision -> ask the user
6. Verify each completed leaf or direct task.
7. Record evidence before reporting completion.

## Execution Feedback And Re-entry

Seungjeongwon treats execution as a way to test planning assumptions.

- If only implementation details differ from the plan, adjust tactics locally, verify, and report the deviation.
- If a leaf's scope, dependency, or verification method is wrong, perform local re-exploration or recommend Uigwe `local_reexploration`.
- If an architecture or design assumption fails, stop widening execution and recommend Uigwe `brainstorming`.
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
