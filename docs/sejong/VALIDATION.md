# Uigwe Validation Plan

**Status:** Draft

## Purpose

This document defines how to validate Uigwe as a planning method and Sejong-facing skill surface.

The goal is not to prove that a plan sounds good. Uigwe should be checked against frozen scenarios, explicit scorecards, bundle validators, and limited consumer dry runs before a planning change is treated as better.

## Validation Principles

- **Baseline first:** compare Uigwe against normal lightweight planning before claiming improvement.
- **Task-specific scoring:** score the planning behaviors Uigwe exists to improve.
- **Contract before taste:** schema, bundle, gate, and handoff contracts must pass before subjective quality scoring matters.
- **Shadow before default:** try Uigwe on real work in parallel before making it the default planning path for a new workflow.

## What To Compare

Use at least two baselines.

### Baseline A: Lightweight Planning

Normal planning without Uigwe packets, goal trees, readiness gates, or re-entry structure.

Examples:

- direct planning conversation
- short implementation plan
- manual requirements capture plus hand-written checklist

### Baseline B: Structured Planning Without Uigwe

Structured planning that does not use Uigwe's packet and goal-tree contract.

Examples:

- interview notes -> option comparison -> manual task list
- design brief -> implementation plan

### Candidate

- Uigwe through `$uigwe`
- Uigwe reached through `$sejong` when Sejong routes to formal planning

## What To Measure

### Sejong-Level Metrics

- `route_sequence_accuracy`: did Sejong choose the expected surface chain or an explicitly acceptable alternative?
- `overplanning_rate`: how often did Sejong invoke Uigwe or teams for direct tasks?
- `missed_research_rate`: how often did Sejong decide or execute before gathering required evidence?
- `decision_quality`: did Jiphyeonjeon compare serious options, reject weaker ones, and name a defensible next surface?
- `execution_success_rate`: did Seungjeongwon complete executable leaves with reproducible verification evidence?
- `guardrail_violation_count`: did workers, hooks, or direct edits violate lead-owned gates, final synthesis, or protected paths?
- `continuity_preservation_rate`: did follow-up turns, pending gates, and compacted context keep the active Sejong workflow intact?
- `artifact_hygiene_rate`: did runtime artifacts stay under the Sejong artifact root unless explicitly promoted?
- `tokens_per_successful_scenario`: how many tokens were spent per passing scenario?
- `quality_delta_per_1k_tokens`: how much benchmark score improved for each additional 1,000 tokens.

### Core Metrics

- `mode_resolution_accuracy`: did Uigwe choose or recover to the correct effective mode?
- `packet_completeness_rate`: did it produce the required artifacts for that mode?
- `bundle_validation_pass_rate`: did the generated bundle pass `validate_bundle.py`?
- `executable_leaf_rate`: how many leaf nodes were truly consumer-ready?
- `consumer_ready_rate`: how often could the plan be handed off without guesswork?
- `plan_acceptance_rate`: how often would a human approve the plan with only light edits?
- `approval_gate_violation_count`: how often did live-session gates get skipped or silently waived?
- `unnecessary_reentry_rate`: how often did Uigwe reopen earlier stages without enough justification?
- `human_edit_distance`: how much rewriting was needed after the generated bundle?
- `minutes_to_usable_plan`: how long it took to reach a usable bundle.

### Secondary Metrics

- `retained_alternative_quality`
- `goal_tree_coherence`
- `verification_clarity`
- `risk_summary_quality`
- `blocked_leaf_diagnosis_quality`

## Validation Phases

### Phase 1: Deterministic Contract Checks

Run these on every Uigwe contract or schema change:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/brownfield-decompose-only
```

### Phase 2: Instruction-Surface Guardrail Benchmark

Run this when changing `.agents/skills`, router docs, README guidance, live-session rules, or validation docs:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
```

This benchmark is deterministic. It checks whether the installed skill surface still exposes the required routing, live-session, output, validation, bounded-parallelism, active-context, hook, protected-route, and repo-context init/refresh contracts.

### Phase 2B: King Sejong Guardrail TDD

Run these when changing active context checkpoints, hooks, TeamExecutor authority, protected self-modification rules, or runtime artifact retention:

```bash
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_context.py
python3 docs/sejong/scripts/test_team_executor.py
python3 docs/sejong/scripts/test_sillok_trace.py
SEJONG_HOME="$(mktemp -d)" python3 docs/sejong/scripts/test_king_sejong_e2e.py
```

Expected red tests before implementation:

- protected Sejong path edits pass without route evidence
- follow-up prompts fail to receive active King Sejong context
- subagents can claim Uigwe gate approval or final synthesis
- `$team` workers can claim final decisions by majority vote
- runtime artifacts affect the target repository working tree

Expected green behavior:

- `UserPromptSubmit` injects active context
- `sejong_context.py` can start, update, diagnose, and close the active context pointer without writing runtime state into the target repository
- `PreToolUse` and `PermissionRequest` guard protected paths
- `SubagentStop` rejects gate and final-authority claims
- `Stop` continues when verification gates remain
- TeamExecutor invalid authority fixtures fail for the expected reason
- Sillok trace events reject private-data, untrusted-content, external-action combinations without a human approval ref
- runtime artifacts stay under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`

### Phase 2C: Sejong Surface Seed Benchmark

Run this when changing Sejong routing, active-session behavior, TeamExecutor guidance, hooks, Seungjeongwon handoff behavior, validation scorecards, or evaluation docs:

```bash
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
```

Use `--write` only when intentionally refreshing the deterministic scorecard artifacts:

```bash
python3 docs/sejong/scripts/benchmark_sejong_surface.py --write --require-targets
```

This benchmark does not call an LLM. It validates that `examples/validation/sejong-seed-task-set.json` remains a complete, gradeable Sejong-level scenario set with route sequences, acceptable alternatives, forbidden surfaces, guardrail expectations, observable artifacts, and resource budgets.

### Phase 3: Frozen Planning Benchmark

Use `examples/validation/uigwe-seed-task-set.json` as the first task set.

For each scenario:

1. run Baseline A
2. fill a scorecard
3. run Baseline B
4. fill a scorecard
5. run Uigwe
6. fill a scorecard
7. compare aggregate metrics and scenario-level deltas

Patch Uigwe only after reviewing where it actually lost.

### Phase 4: Shadow Planning

Run Uigwe in parallel on real work without making it authoritative.

Recommended sample:

- `5` small greenfield tasks
- `5` small brownfield tasks

Use this to find scenario types the frozen benchmark missed.

### Phase 5: Limited Consumer Dry Run

Take a small subset of Uigwe `executable_leaf` nodes and hand them to the Codex consumer or Seungjeongwon path.

Record the result with:

- `consumer-dry-run-result.schema.json`
- `codex-consumer-feedback.schema.json`

Do not claim full consumer readiness from a limited dry run. Use it to expose whether leaves are actually executable.

### Phase 6: Scorecard Comparison

Compare a baseline scorecard and candidate scorecard before promoting a Sejong or Uigwe behavior change:

```bash
python3 docs/sejong/scripts/compare_scorecards.py <baseline.scorecard.json> <candidate.scorecard.json> --require-non-regression
```

When the scorecards include `resource_usage`, review:

- `quality_delta`
- `token_ratio`
- `cost_ratio`
- `cost_normalized_gain`
- scenario-level regressions

Token and cost deltas are secondary metrics. They should not hide a real quality improvement, but a candidate that spends substantially more tokens without score gains should not be promoted by default.

## Recommended Promotion Gates

Do not promote a planning-method change unless the frozen benchmark and shadow runs meet these first-pass targets:

- `mode_resolution_accuracy >= 0.80`
- `packet_completeness_rate >= 0.90`
- `bundle_validation_pass_rate >= 0.90`
- `executable_leaf_rate >= 0.85`
- `consumer_ready_rate >= 0.80`
- `plan_acceptance_rate >= 0.70`
- `approval_gate_violation_count == 0`
- `unnecessary_reentry_rate <= 0.15`
- `median_human_edit_distance` improves over Baseline B
- Sejong surface benchmark has no partial or failing scenarios
- scorecard comparison has no scenario-level regressions for protected guardrail scenarios
- if `token_ratio > 1.25`, require either `quality_delta >= 0.10` or an explicit overhead justification
- if `token_ratio > 1.50` and `quality_delta < 0.05`, hold the change for redesign

These are initial targets, not permanent truth.

## How To Grade

Code-grade what can be checked mechanically:

- schema validity
- bundle validity
- artifact presence
- required field completeness
- expected mode match
- instruction-surface guardrail preservation

Human or LLM-grade what needs judgment:

- whether re-entry was appropriate
- whether retained alternatives were meaningful
- whether a human would approve the plan with light edits
- whether leaves are truly executable

Prefer bounded judgments:

- `pass`
- `partial`
- `fail`

or numeric scores in `[0, 1]`.

## Current Deliverables

This validation pack includes:

- this plan
- task-set and scorecard schemas
- a seed frozen planning task set
- a seed Sejong surface task set
- an instruction-surface task set
- a scorecard template
- a deterministic instruction-surface benchmark runner
- a deterministic Sejong surface benchmark runner
- a scorecard comparison helper with token and cost deltas
- a Sillok trace-event schema for evidence, verification, handoff, and security-review records
- King Sejong hook, TeamExecutor, and end-to-end guardrail tests
- a run output directory for benchmark scorecards

## Failure Cases

Treat Uigwe as failing a scenario when:

- it chooses the wrong entry mode and does not recover
- it generates incomplete packets for the chosen mode
- it skips or silently waives live-session approval gates
- it marks non-executable nodes as executable leaves
- it repeatedly re-enters earlier stages without improving plan quality
- the plan still requires major human restructuring

## Why Real Usage Is Not Enough

Real usage is necessary, but it is not enough.

It helps discover friction, missing scenarios, and handoff problems. It does not prove that Uigwe beats the existing planning workflow, that re-entry is improving quality, or that leaf execution is safer.
