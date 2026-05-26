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

## Runtime State

Runtime state belongs under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

Do not use `.omx` paths as Sejong state.

Target repositories should not receive Sejong runtime files unless the user explicitly asks to promote a reviewed artifact. This rule covers active contexts, ambiguity registers, TeamExecutor mailboxes, Seungjeongwon run artifacts, attempt ledgers, outcome comparisons, and Sillok traces.

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
