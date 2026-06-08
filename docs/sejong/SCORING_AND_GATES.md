# Uigwe Scoring And Gates

**Status:** Draft

## Purpose

This document turns Uigwe planning rules and Seungjeongwon actionable-readiness rules into default numeric policy.

These defaults are not meant to freeze Uigwe permanently. They exist so the protocol can:

- rank handoff decomposition candidates consistently
- decide when a packet is ready enough to skip into a later stage
- decide when local repair is enough
- decide when to re-enter `brainstorming` or `deep-interview`
- decide when Seungjeongwon todo decomposition has reached actionable-leaf readiness

The matching machine-facing defaults live in:

- `policy.defaults.json`
- `policy.defaults.schema.json`

## Metric Families

The Sejong planning/execution contract uses three distinct metric families.

### 1. Candidate Priority Score

Used during `Backtracking + BFS Decomposition` to rank surviving candidates after hard gates.

Formula:

`priority = w_goal * goal_contribution + w_confidence * confidence + w_verify * verification_clarity + w_dependency * dependency_simplicity + w_cost * (1 - cost) + w_risk * (1 - risk)`

Notes:

- `cost` and `risk` are stored as penalties, so Uigwe converts them into efficiencies with `1 - value`
- this score does not override hard gates
- this score ranks candidates relative to their siblings, not against the whole graph

### 2. Packet Readiness Score

Used to decide whether Uigwe may enter a later stage without re-running an earlier one.

Derived readiness metrics:

- `intent_readiness`
- `design_readiness`
- `handoff_readiness`
- `actionable_readiness`

These are weighted completeness-and-clarity scores computed by the orchestrator from packet contents and planning analysis.

`handoff_readiness` belongs to Uigwe and decides whether a node can be handed to Seungjeongwon. `actionable_readiness` belongs to Seungjeongwon and decides whether executor-side todo decomposition may enter the execution attempt loop.

Completion uses a separate score family. `execution_guardrail_score` belongs to
the Uigwe-to-Seungjeongwon execution contract and decides whether a completed
leaf or completed run can be claimed. It is intentionally stricter than
`actionable_readiness`: actionable readiness means "safe to try"; guardrail
completion means "proved enough to close."

### 3. Re-entry Thresholds

Used to decide whether to:

- retry locally
- re-enter `brainstorming`
- re-enter `deep-interview`

These thresholds are not based on a single score alone. Uigwe combines:

- score deltas
- blocked ratios
- invalidation counts
- contradiction counts
- retry exhaustion

## Derived Readiness Dimensions

### Intent Readiness

Suggested derived dimensions:

- `goal_clarity`
- `why_now_clarity`
- `scope_clarity`
- `non_goal_clarity`
- `decision_boundary_clarity`
- `constraint_clarity`
- `acceptance_clarity`
- `open_question_resolution`

Default weights:

- `goal_clarity`: `0.20`
- `why_now_clarity`: `0.10`
- `scope_clarity`: `0.15`
- `non_goal_clarity`: `0.15`
- `decision_boundary_clarity`: `0.15`
- `constraint_clarity`: `0.10`
- `acceptance_clarity`: `0.10`
- `open_question_resolution`: `0.05`

### Design Readiness

Suggested derived dimensions:

- `problem_frame_quality`
- `selected_approach_quality`
- `alternatives_quality`
- `tradeoff_clarity`
- `decision_coherence`
- `assumption_quality`
- `risk_quality`
- `validation_plan_quality`

Default weights:

- `problem_frame_quality`: `0.14`
- `selected_approach_quality`: `0.20`
- `alternatives_quality`: `0.16`
- `tradeoff_clarity`: `0.16`
- `decision_coherence`: `0.12`
- `assumption_quality`: `0.08`
- `risk_quality`: `0.08`
- `validation_plan_quality`: `0.06`

### Handoff Readiness

Suggested Uigwe-derived dimensions:

- `objective_clarity`
- `done_clarity`
- `scope_boundary_clarity`
- `dependency_clarity`
- `verification_expectation_clarity`
- `reentry_trigger_clarity`
- `executor_context_clarity`

Default weights:

- `objective_clarity`: `0.20`
- `done_clarity`: `0.18`
- `scope_boundary_clarity`: `0.16`
- `dependency_clarity`: `0.12`
- `verification_expectation_clarity`: `0.16`
- `reentry_trigger_clarity`: `0.14`
- `executor_context_clarity`: `0.14`

### Actionable Readiness

Suggested Seungjeongwon-derived dimensions:

- `task_specificity`
- `first_action_clarity`
- `done_observability`
- `execution_scope_narrowness`
- `dependency_satisfaction`
- `fresh_verification_clarity`
- `failure_path_clarity`

Default weights:

- `task_specificity`: `0.18`
- `first_action_clarity`: `0.16`
- `done_observability`: `0.16`
- `execution_scope_narrowness`: `0.14`
- `dependency_satisfaction`: `0.12`
- `fresh_verification_clarity`: `0.16`
- `failure_path_clarity`: `0.08`

### Execution Guardrail Score

Suggested Seungjeongwon completion dimensions, set by Uigwe before handoff:

- `done_criteria_satisfaction`
- `verification_evidence_quality`
- `scope_containment`
- `dependency_integrity`
- `regression_safety`
- `reentry_signal_resolution`
- `artifact_traceability`

Default weights:

- `done_criteria_satisfaction`: `0.24`
- `verification_evidence_quality`: `0.20`
- `scope_containment`: `0.14`
- `dependency_integrity`: `0.12`
- `regression_safety`: `0.12`
- `reentry_signal_resolution`: `0.10`
- `artifact_traceability`: `0.08`

These dimensions are scored from `0.0` to `1.0` from the execution evidence.
They do not replace hard binary constraints such as "Uigwe contract preserved",
"no open blocker", or "no unresolved re-entry request." Binary hard constraints
must be true; they are not averaged into a `0.98` score.

## Default Profiles

### Greenfield

Use when:

- the system or feature shape is still emerging
- solution space exploration matters more than integration precision

#### Candidate Priority Score Weights

- `goal_contribution`: `0.27`
- `confidence`: `0.18`
- `verification_clarity`: `0.12`
- `dependency_simplicity`: `0.09`
- `cost_efficiency`: `0.12`
- `risk_efficiency`: `0.22`

#### Readiness Thresholds

- `intent_readiness` required for `brainstorming`: `0.68`
- `design_readiness` required for `decomposition`: `0.70`
- `handoff_readiness` required for Seungjeongwon handoff: `0.78`
- `actionable_readiness` required for execution attempt: `0.82`
- `leaf_guardrail_minimum` required for every completion guardrail: `0.98`
- `leaf_guardrail_aggregate` required to close an actionable leaf: `0.98`
- `run_guardrail_aggregate` required to close the run: `0.98`
- `selected_leaf_coverage` required to close the run: `1.00`
- `success_criteria_coverage` required to close the run: `1.00`

#### Frontier Defaults

- beam width by depth:
  - `0`: `3`
  - `1`: `3`
  - `2`: `2`
  - `3+`: `1`
- retained alternatives by depth:
  - `0`: `3`
  - `1`: `3`
  - `2`: `2`
  - `3+`: `0`
- max handoff decomposition candidates generated per node: `3`
- local subtree retry limit before escalation: `2`

#### Re-entry Thresholds

- local re-exploration if best local alternative beats current branch by `>= 0.08`
- re-enter `brainstorming` if best retained alternative beats current selected branch by `>= 0.15`
- re-enter `brainstorming` if subtree blocked-or-invalidated ratio reaches `>= 0.35`
- re-enter `deep-interview` if upstream assumption invalidations reach `>= 2`
- re-enter `deep-interview` immediately on any confirmed `non_goal` contradiction
- re-enter `deep-interview` immediately on any confirmed `decision_boundary` contradiction
- re-enter `deep-interview` if `brainstorming` re-entry has already happened `2` times without restoring stability

### Brownfield

Use when:

- existing codebase behavior and integration constraints dominate planning quality

#### Candidate Priority Score Weights

- `goal_contribution`: `0.22`
- `confidence`: `0.14`
- `verification_clarity`: `0.20`
- `dependency_simplicity`: `0.18`
- `cost_efficiency`: `0.08`
- `risk_efficiency`: `0.18`

#### Readiness Thresholds

- `intent_readiness` required for `brainstorming`: `0.72`
- `design_readiness` required for `decomposition`: `0.76`
- `handoff_readiness` required for Seungjeongwon handoff: `0.84`
- `actionable_readiness` required for execution attempt: `0.88`
- `leaf_guardrail_minimum` required for every completion guardrail: `0.98`
- `leaf_guardrail_aggregate` required to close an actionable leaf: `0.98`
- `run_guardrail_aggregate` required to close the run: `0.98`
- `selected_leaf_coverage` required to close the run: `1.00`
- `success_criteria_coverage` required to close the run: `1.00`

#### Frontier Defaults

- beam width by depth:
  - `0`: `2`
  - `1`: `2`
  - `2`: `2`
  - `3+`: `1`
- retained alternatives by depth:
  - `0`: `2`
  - `1`: `2`
  - `2`: `1`
  - `3+`: `0`
- max handoff decomposition candidates generated per node: `3`
- local subtree retry limit before escalation: `2`

#### Re-entry Thresholds

- local re-exploration if best local alternative beats current branch by `>= 0.06`
- re-enter `brainstorming` if best retained alternative beats current selected branch by `>= 0.12`
- re-enter `brainstorming` if subtree blocked-or-invalidated ratio reaches `>= 0.25`
- re-enter `deep-interview` if upstream assumption invalidations reach `>= 2`
- re-enter `deep-interview` immediately on any confirmed `non_goal` contradiction
- re-enter `deep-interview` immediately on any confirmed `decision_boundary` contradiction
- re-enter `deep-interview` if `brainstorming` re-entry has already happened `2` times without restoring stability

## Readiness Gate Interpretation

Readiness thresholds should be treated as necessary but not sufficient.

For example, a `design_readiness` score above threshold still does not justify decomposition when:

- approval is still pending
- the selected approach is missing
- alternatives were never seriously compared
- the selected approach lacks a Decision Justification record for material trade-offs
- critical assumptions remain unresolved

Likewise, a Uigwe leaf may not be marked `handoff_leaf` if:

- file scope is still ambiguous
- verification is nominal rather than actionable
- re-entry triggers are missing
- the handoff choice cannot explain why this leaf is needed instead of a simpler viable alternative
- Seungjeongwon would still need to guess planning boundaries

Likewise, a Seungjeongwon todo may not be marked `actionable_leaf` if:

- the first edit, command, or inspection target is missing
- the task is still broad enough to need subtodo decomposition
- dependency prerequisites are neither satisfied nor explicitly blocked
- verification cannot produce fresh proof
- failure would not produce a next hypothesis or escalation target

A Seungjeongwon actionable leaf may not be marked `completed` if:

- any Uigwe-defined leaf completion guardrail scores below `0.98`
- the leaf aggregate execution guardrail score is below `0.98`
- the Uigwe goal, non-goals, success criteria, verification bar, or
  must-preserve behavior changed without Uigwe re-entry
- verification evidence is stale, missing, or disconnected from the leaf's
  `done_criteria`
- dependency or regression checks are unresolved
- the recommended re-entry target is anything other than `none`

A Seungjeongwon run may not be marked `completed` if:

- any selected actionable leaf is still open, blocked, invalidated, or below its
  leaf completion guardrail threshold
- run aggregate execution guardrail score is below `0.98`
- selected leaf coverage is below `1.00`
- success criteria coverage is below `1.00`
- any blocker, unresolved re-entry request, or external gate is hidden behind a
  generic done claim

## Re-entry Precedence

When several triggers fire at once, Uigwe should prefer the highest-level valid re-entry target.

Priority:

1. `deep-interview`
2. `brainstorming`
3. `local_reexploration`

This prevents repeated local repair when the actual issue is upstream intent or design instability.

## Tuning Guidance

Raise thresholds when:

- the domain is safety-critical
- verification is expensive
- integration risk is high

Lower thresholds carefully when:

- the task is intentionally exploratory
- iteration speed matters more than early formal precision
- the consumer layer can cheaply surface and recover from local blocks

## Current Non-Goals

This draft does not yet define:

- project-specific overrides
- adaptive threshold tuning from historical execution success
- automatic confidence calibration from reviewer disagreement
