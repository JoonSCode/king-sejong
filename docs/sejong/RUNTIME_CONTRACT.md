# King Sejong Runtime Contract

**Status:** Draft

## Purpose

This document defines the runtime contract for King Sejong when it is installed into a Codex environment.

King Sejong is Codex-native. It does not replace Codex, user permissions, shell tools, native subagents, host-native teams, or repository instructions. The installed skill files remain thin; durable behavior belongs in this docs tree and is enforced where possible through schemas, deterministic helpers, hooks, and verification commands.

## Contract Layers

Use the lightest layer that can actually enforce the behavior:

- `Skill surface`: routes the user's request into Sejong, JangYeongsil, Jiphyeonjeon, Uigwe, or Seungjeongwon.
- `Contract docs`: define the behavior future maintainers should preserve.
- `Schemas`: make runtime artifacts checkable.
- `Reference scripts`: validate, compare, or manage those artifacts.
- `Hooks`: inject active context and block supported premature completion paths.
- `Final verification`: proves the actual task result met its success criteria.

Prompt text alone is not the enforcement mechanism. It is only the entrypoint into the contract.

Discipline gates are the why-based bridge between instruction text and runtime
behavior. [DISCIPLINE_GATES.md](DISCIPLINE_GATES.md) defines each gate by the
failure it prevents, the owning Sejong surface, the force level (`hard`,
`route`, `advisory`, or `shadow`), and the verification evidence required before
promotion or completion.

## Runtime State

Runtime state belongs under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

Do not use `.omx` paths as Sejong state.

Target repositories should not receive Sejong runtime files unless the user explicitly asks to promote a reviewed artifact. This rule covers active contexts, ambiguity registers, TeamExecutor mailboxes, Seungjeongwon run artifacts, attempt ledgers, outcome comparisons, and Sillok traces.
It also covers workflow-run artifacts used to shadow Codex-migrated dynamic
workflow, deep-research-style, ultracode-style, host-native team, or
TeamExecutor backend candidates.

## Active Context

The active context checkpoint follows [king-sejong-context.schema.json](king-sejong-context.schema.json). It is the compact cross-hook checkpoint for:

- active route and current surface
- pending gates
- protected paths
- ambiguity-register refs
- Seungjeongwon run refs
- TeamExecutor refs
- evidence refs
- exit conditions

Hooks may block `Stop` or `PreCompact` when the active context is incomplete, a referenced ambiguity register is open or broken, or a referenced Seungjeongwon run is active or invalid.

## Long-Run Execution

Long-running unattended work should use Uigwe plus Seungjeongwon:

```text
Uigwe clarifies the idea and design
-> Uigwe defines success criteria, verification methods, and re-entry triggers
-> Seungjeongwon decomposes into actionable todos
-> Seungjeongwon executes, verifies, records attempts, and retries
-> Stop only when pass criteria are met, blocked, invalidated, or re-entry is required
```

The active Seungjeongwon run artifact follows [seungjeongwon-run.schema.json](seungjeongwon-run.schema.json). Use `docs/sejong/scripts/seungjeongwon_run.py` to create and check that artifact.

For explicit Long-Session Outcome Entry requests, active context must be checked against the new objective before execution resumes. A stale active context from another task does not satisfy a new long-session goal. Refresh the route, surface, pending gates, artifact refs, and `task_class` when the user asks for `장기실행`, `긴 세션`, `끝까지`, `long-session`, or an equivalent persistent outcome loop. Small direct commands still bypass this path.

Task class is part of long-session evidence because promotion is class-specific. Record whether the request is `strategy-research-synthesis`, `code-review-defect-analysis`, `small-artifact`, `simple-direct`, or another explicitly named class. For `code-review-defect-analysis`, the context must include a defect-first critic requirement before Uigwe handoff: identify concrete failure modes, distinguish confirmed defects from test gaps, keep fixes proportional, and avoid hiding actionable defects behind broad process advice.

When Seungjeongwon uses or evaluates a workflow-like backend, create a separate
[workflow-run.schema.json](workflow-run.schema.json) artifact and check it with
`docs/sejong/scripts/sejong_workflow_run.py`. That artifact records mapped
surfaces, backend provenance, bounded workers, worker/concurrency metrics,
evidence ledgers, authority violations, and baseline-vs-candidate quality
comparison. It is subordinate runtime evidence; it must not replace Uigwe
packets, route ownership, final synthesis, or final verification.

Workflow-like backends are Codex-native, host-native, TeamExecutor, manual
shadow, or mocked equivalents. Do not invoke Claude CLI, Claude API, or an
external Claude workflow runtime from behind Sejong. If a source idea comes from
another agent system, migrate the behavior into Codex-owned execution or model
it as a mock before promotion.

## Context Stack

King Sejong behavior should be constrained by layered context, artifacts, and checks rather than prompt wording alone.

The normal context stack is:

- source-of-truth docs and thin skill front doors
- discipline gates that explain why a behavior is enforced and how strongly
- active King Sejong context with route, surface, gates, refs, and exit conditions
- ambiguity registers for live clarification state when material uncertainty remains
- Uigwe packets and handoff contracts for selected direction, decision boundaries, success criteria, verification, and re-entry triggers
- Seungjeongwon run artifacts, visible boards, attempt ledgers, and verification evidence during execution
- workflow-run artifacts for shadowed or limited external backends, with
  mapped surfaces, evidence ledgers, and outcome-quality deltas
- hooks, permission policy, schemas, examples, and deterministic benchmarks as guardrails and regression checks

Host features such as Plan mode or `PLANS.md`-style living plans can improve live clarification and long-running execution continuity, but they do not override the Uigwe contract, Seungjeongwon run state, or explicit user approval gates.

## Result Quality

Behavioral guardrails are necessary but not sufficient. A Sejong change is not better merely because routing, hooks, or todo events fired correctly.

For outcome work, compare the resulting work product against the same acceptance criteria. Use [OUTCOME_EVALUATION.md](OUTCOME_EVALUATION.md) and `docs/sejong/scripts/outcome_quality_evaluator.py` for deterministic paired comparisons such as the TagBack growth scenario.

## Optional Codex Guidance

The installer can print or write a compact generic Codex guidance block:

```bash
bash scripts/install-sejong.sh --print-codex-guidance
bash scripts/install-sejong.sh --scope user --codex-guidance user
```

This is optional. It should help Codex discover the installed Sejong contract, but it must not copy this source repository's `AGENTS.md` into target repositories and must not introduce wrapper-specific dependencies.

## Limits

Hooks are guardrails, not a sandbox. They do not intercept every possible equivalent action, prove product success, or replace human approval for external actions.

For product, marketing, or strategy outcomes, Sejong can produce a better plan and measurement loop, but real success still requires external evidence such as user behavior, analytics, market response, or A/B tests.

Use `docs/sejong/scripts/product_evidence_gate.py` before claiming product success. A valid field-validation plan proves only that the next test is ready; success requires result evidence from analytics, a controlled experiment, and user research.
