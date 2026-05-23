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

This benchmark is deterministic. It checks whether the installed skill surface still exposes the required routing, live-session, output, validation, bounded-parallelism, active-context, hook, and protected-route contracts.

### Phase 2B: King Sejong Guardrail TDD

Run these when changing active context checkpoints, hooks, TeamExecutor authority, protected self-modification rules, or runtime artifact retention:

```bash
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_team_executor.py
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
- `PreToolUse` and `PermissionRequest` guard protected paths
- `SubagentStop` rejects gate and final-authority claims
- `Stop` continues when verification gates remain
- TeamExecutor invalid authority fixtures fail for the expected reason
- runtime artifacts stay under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`

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
- an instruction-surface task set
- a scorecard template
- a deterministic instruction-surface benchmark runner
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
