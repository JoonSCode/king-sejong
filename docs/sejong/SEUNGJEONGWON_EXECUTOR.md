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

Uigwe also owns the numeric completion guardrails that decide when
Seungjeongwon may close an actionable leaf or the overall run. The default
completion threshold is `0.98` for every leaf guardrail, `0.98` for the leaf
aggregate, and `0.98` for the run aggregate. Selected leaf coverage and success
criteria coverage default to `1.00`. Seungjeongwon must keep decomposing,
retrying, blocking, or escalating until those scores pass; it must not lower the
thresholds or silently average away a failed hard guardrail.

## Execution Default

The native default is:

- execute in Codex through Seungjeongwon
- verify in Codex
- report execution feedback directly

For a handoff-ready Uigwe bundle whose original request asks for an outcome to be completed, Seungjeongwon should attach execution to a host-native goal automatically when that surface is available. The user does not need to type `/goal` separately after Uigwe has produced the execution contract.

Native goal backing is a runtime persistence aid, not the execution plan. The goal should contain the approved objective, completion criteria, verification evidence requirements, blocker policy, and Uigwe re-entry triggers. Seungjeongwon keeps the detailed todo list, replacements, redefinitions, attempt hypotheses, and verification steps in the visible execution board and execution feedback.

Do not activate a native goal for research-only, advice-only, plan-only, open-ambiguity, non-handoff-ready, or tiny Sejong-direct maintenance work. If the host lacks native goal support, continue with the normal Seungjeongwon loop and record that native goal support was unavailable when structured execution feedback is produced.

For long-running or compaction-sensitive work, Seungjeongwon should also maintain a `sejong.seungjeongwon-run/v0.1-draft` artifact. The artifact records the approved goal, success criteria, verification methods, active todos, attempt ledger, verification evidence, blockers, and Uigwe re-entry requests. Hooks can block `Stop` and `PreCompact` when this artifact is active or invalid.

When Seungjeongwon evaluates or uses a workflow-like backend such as migrated
dynamic workflow concepts, `/deep-research`-style research fan-out,
ultracode-style orchestration, Codex native subagents, host-native team
messaging, TeamExecutor workers, or Codex-side mocks, it should also maintain a
`sejong.workflow-run/v0.1-draft` artifact. The workflow-run artifact records
the mapped court surfaces, backend mode, bounded workers, allowed outputs,
backend provenance, worker/concurrency metrics, evidence ledger, authority
violations, quality comparison, and final recommendation. It is execution or
research evidence only; it cannot approve Uigwe gates, claim consensus, replace
final synthesis, or complete final verification.

Seungjeongwon must not invoke Claude CLI, Claude API, or an external Claude
workflow runtime as a hidden backend. External workflow ideas may be migrated to
Codex-native execution, represented by `codex_mock_workflow`, or kept in shadow
until a Codex-owned implementation is justified.

## Execution Inputs

For a Uigwe bundle:

- bundle directory or `wrapper.result.json`
- selected handoff leaf ids, or all handoff leaves by default
- optional git policy from the user or repo rules
- optional native goal id, or enough Uigwe handoff data to create an implicit native goal when the host supports it

For direct action:

- explicit user request
- target files or repo scope when relevant
- done criteria
- verification command or observable proof when known

Direct action is exceptional. It is for clear non-goal maintenance or user-explicit direct scope when no Uigwe handoff contract is active. When a validated Uigwe bundle or handoff-ready Uigwe state exists, Seungjeongwon must execute from that contract rather than letting Sejong direct or ordinary direct edits bypass the executor.

## Execution Rules

1. Read the source of truth before editing.
2. Identify dependency-ready handoff leaves or direct scope.
3. Run executor-side todo decomposition until the selected work is represented as actionable leaves.
4. Execute only actionable leaves derived from the approved handoff leaves or explicit direct scope.
5. Preserve planning and execution boundaries:
   - planning uncertainty -> return to Uigwe
   - implementation failure -> debug and continue
   - blocked external decision -> ask the user
6. For validation-heavy work, decompose the verification objective into task-specific verification perspectives before judging the result.
7. Verify each completed actionable leaf or direct task.
8. Record evidence before reporting completion.

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

When native goal backing is active, the same loop remains authoritative. Failed verification should update the visible board or attempt ledger before any goal status changes. Mark the native goal complete only after the Uigwe success criteria are satisfied with fresh verification evidence. Mark it blocked only when blocker evidence shows no meaningful local progress is possible without user input, external state change, or Uigwe re-entry.

If the 4-6 loop keeps failing because the todo is too broad, dependency order is wrong, or the first implementation hypothesis was weak, Seungjeongwon continues local decomposition. If the handoff leaf itself is wrong, it recommends Uigwe `local_reexploration`. If the chosen design is wrong, it recommends `brainstorming`. If the goal, non-goals, success criteria, or must-preserve behavior are incomplete or contradicted, it recommends `deep_interview` or `human_review`.

## Visible Execution Board

When Codex todo tooling is available, Seungjeongwon uses it as the user-visible execution board.

Before implementation begins, publish the initial actionable leaf list through Codex todo/update_plan. The visible board should show the current handoff leaf, actionable todos, dependency order, and verification-oriented work. It is not a private scratchpad and should not hide material execution reshaping from the user.

Seungjeongwon must not silently overwrite an existing visible todo when execution changes the shape of the work. If scope, dependency order, done criteria, or verification method changes, append a redefinition event todo such as `R1: redefine execution todo after failed activation proof`, mark the old todo as replaced or invalidated in the visible text when the tooling has only basic statuses, and add the replacement todo as a new item.

Use the execution attempt ledger, not new visible todos, for small implementation hypotheses that stay inside the same actionable todo. A visible redefinition event is required when the actionable todo itself changes. Uigwe re-entry is required when the approved goal, non-goals, success criteria, must-preserve behavior, verification bar, or other guardrails become unstable.

When execution feedback is persisted or handed back as JSON, record the same user-visible board movement in `visible_todo_events`. This ordered event list should include initial publication, starts, verification results, redefinitions, replacements, completions, blocks, or `board_unavailable` when the host lacks todo tooling. A typical visible reshaping sequence is `T2` published, `T2` verification fails, `R1` records the redefinition, `T2` is marked replaced, and replacement todos `T2a` and `T2b` are added before execution continues.

## Verification Decomposition Loop

When the work is to validate, compare, review, prove readiness, or decide whether a new behavior is actually better, Seungjeongwon treats verification itself as an execution objective.

Before judging the result, list the task-specific verification perspectives needed for that objective. The perspectives are not fixed, but typical examples include:

- contract and scope preservation
- result quality against acceptance criteria
- evidence quality and unsupported-claim risk
- regression or compatibility risk
- actionability and owner split
- verification or measurement plan quality
- cost, turn, tool-call, or operational overhead
- safety, privacy, or guardrail risk

For each perspective, define:

- verification question
- evidence target
- method or command
- sufficiency threshold
- falsification signal
- owner or responsibility boundary
- first action

Then verify the verification plan before executing it. A perspective is weak when it is too broad, unmeasurable, disconnected from acceptance criteria, missing evidence, duplicative, or likely to produce only a subjective opinion. Weak perspectives are split, replaced, or escalated the same way weak actionable todos are.

This loop is recursive:

```text
verification goal
-> perspective listup
-> perspective verification
-> sub-perspective decomposition
-> execute verification
-> judge result quality
-> add, replace, or close perspectives
```

For paired comparisons, such as baseline execution versus implicit native goal handoff, Seungjeongwon must compare the resulting work products against the same acceptance criteria. Do not promote a candidate only because the route, goal activation, or visible board behavior worked. Promote it only when the final result is better enough to justify the overhead, or keep it shadowed when evidence is inconclusive.

For harness, orchestrator, architecture, refactoring, revision, or addition
requests that ask Seungjeongwon to try many improvement hypotheses, first use
the orchestrator hypothesis matrix as the measurement contract:

```bash
python3 docs/sejong/scripts/benchmark_orchestrator_hypothesis_matrix.py --require-targets
```

The matrix must evaluate at least ten hypotheses per improvement area, use the
same weighted dimensions for every candidate, record reviewable evidence and
verification refs, and apply `tie_breaker_dimensions` when primary scores are
equal. A tied result is not adoption evidence until the measurement is refined
enough to select a unique passing hypothesis or record a blocker.
Candidate scores must come from executable trial cases and candidate capability
profiles rather than handwritten preference scores.
The adopted candidate must also align with an operational corpus of existing
King Sejong validation, workflow-run, outcome-evaluation, and integrated-quality
evidence refs before Seungjeongwon treats it as a stronger improvement.

For workflow-like backends, record the same paired comparison in a
`workflow-run.json` artifact and validate it with:

```bash
python3 docs/sejong/scripts/sejong_workflow_run.py check --path <workflow-run.json>
```

Before selecting a workflow backend for an execution leaf, Seungjeongwon may run
the task-class delegation gate:

```bash
python3 docs/sejong/scripts/task_class_delegation_gate.py --task-class implementation
```

The gate is deterministic and may select `direct_execution`,
`bounded_subagents`, `team_executor`, `research_fanout`, or
`no_write_dry_run`. Its hard gates preserve Uigwe authority, keep worker output
as evidence only, require reviewable evidence, keep runtime artifacts under
Sejong home or promoted refs, and reject new court-mode creation. A dry-run
selection is blocker evidence, not permission to weaken the Uigwe or
Seungjeongwon verification bar.

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

An actionable leaf is `completed` only when:

- every Uigwe-defined numeric completion guardrail for that leaf is at least
  `0.98` unless the Uigwe bundle explicitly sets a higher or lower threshold
- the leaf aggregate guardrail score is at least `0.98`
- the leaf's `done_criteria` are satisfied by fresh verification evidence
- scope, dependency, regression, and re-entry guardrails are resolved
- the recommended Uigwe re-entry target is `none`
- hard binary guardrails are true rather than averaged into the score

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

Use the reference helper when a machine-checkable active run artifact is useful:

```bash
python3 docs/sejong/scripts/seungjeongwon_run.py start --path <run.json> --run-id <id> --goal "..." --success-criterion "..." --verification-method "..."
python3 docs/sejong/scripts/seungjeongwon_run.py record-attempt --path <run.json> --todo-id T1 --hypothesis "..." --action "..." --verification "..." --result pass --finding "..." --next-decision "..."
python3 docs/sejong/scripts/seungjeongwon_run.py check --path <run.json>
```

Use the workflow-run helper when a machine-checkable backend shadow comparison
is useful:

```bash
python3 docs/sejong/scripts/sejong_workflow_run.py start --path <workflow-run.json> --run-id <id> --workflow-kind dynamic_workflow --workflow-name "..." --backend codex_mock_workflow --mapped-surface seungjeongwon --source-of-truth-ref docs/sejong/VALIDATION.md --success-criterion "..."
python3 docs/sejong/scripts/sejong_workflow_run.py record-metrics --path <workflow-run.json> --worker-count 3 --max-concurrency 3 --unsupported-claim-count 0 --token-or-cost-overhead-ref benchmark:workflow-run --write-scopes-disjoint
python3 docs/sejong/scripts/sejong_workflow_run.py record-comparison --path <workflow-run.json> --baseline-result-ref baseline --candidate-result-ref candidate --acceptance-criterion "..." --outcome-quality-delta 0.1 --overhead-ratio 1.2 --recommendation keep_shadowing
python3 docs/sejong/scripts/sejong_workflow_run.py check --path <workflow-run.json>
```

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

## Completion State Split

Before any completion, readiness, or deployability claim, Seungjeongwon must
split the state being claimed.

Required fields in the human-facing closeout:

- local implementation state: what changed locally and whether that local scope
  is implemented
- canonical repo or branch state: current repo, branch or worktree, dirty state,
  commit or integration status, and whether the canonical target contains the
  work
- verification evidence: fresh tests, builds, schema checks, runtime checks, or
  explicit evidence gaps
- external gate state: account, App Store, CloudKit, device, production data,
  user research, or other gates that cannot be proven by local commands
- warnings or residual risk: known warnings, noisy logs, unsupported
  environments, stale evidence, or manual checks still needed

For app distribution questions such as "is this deployable?": Local simulator tests and Release builds can prove local readiness only. They do not prove TestFlight upload, App Store Connect setup, CloudKit multi-account sharing, eligible-device AI behavior, or real-user quality unless those exact checks have fresh evidence.

If the user asks for a single answer, answer directly but keep the split
visible. Do not compress separate states into one "done" claim.

## Output Contract

Seungjeongwon reports:

- `status`: `completed`, `blocked`, `invalidated`, or `failed`
- completed leaf ids or Sejong direct scope
- blocked or invalidated scope with reason
- files changed or artifacts produced
- actionable decomposition evidence
- visible todo board updates, including replacement or redefinition events when they occurred
- `visible_todo_events` when machine-readable execution feedback is produced
- `verification_perspectives` when validation-heavy work decomposes verification into perspectives
- `paired_result_comparison` when baseline and candidate outputs are compared against the same acceptance criteria
- execution attempt ledger summary
- leaf-level and run-level execution guardrail scores
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

Seungjeongwon applies the hard execution discipline gates from
[DISCIPLINE_GATES.md](DISCIPLINE_GATES.md), especially `Root Cause Before Fix`,
`Verification Before Completion`, and `No Silent Success Redefinition`. These
gates mean the executor may adapt tactics, split todos, and retry hypotheses,
but it must not claim completion without fresh evidence or change the approved
Uigwe success contract to make verification pass.

Acceptable evidence includes:

- tests, typecheck, lint, build, or schema validation output
- bundle validation output
- manual runtime check with clear observed result
- git status and commit evidence when closeout is requested
- explicit blocker evidence when completion is not possible

When a `sejong.seungjeongwon-run/v0.1-draft` artifact is used, completed todos
must carry guardrail scores and at least one attempt. Completed runs must have no
open todos, fresh verification evidence, and run-level guardrail scores. The
reference helper rejects completed todos or runs whose guardrail scores fall
below the configured thresholds.
