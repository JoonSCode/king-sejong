# Uigwe Scoring And Gates

**Status:** Draft

## Purpose

This document turns Uigwe's qualitative planning rules into default numeric policy.

These defaults are not meant to freeze Uigwe permanently. They exist so the protocol can:

- rank decomposition candidates consistently
- decide when a packet is ready enough to skip into a later stage
- decide when local repair is enough
- decide when to re-enter `brainstorming` or `deep-interview`

The matching machine-facing defaults live in:

- `policy.defaults.json`
- `policy.defaults.schema.json`

## Metric Families

Uigwe uses three distinct metric families.

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
- `leaf_readiness`

These are weighted completeness-and-clarity scores computed by the orchestrator from packet contents and planning analysis.

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

### Leaf Readiness

Suggested derived dimensions:

- `task_clarity`
- `done_clarity`
- `file_scope_clarity`
- `dependency_clarity`
- `verification_clarity`
- `consumer_context_clarity`

Default weights:

- `task_clarity`: `0.22`
- `done_clarity`: `0.18`
- `file_scope_clarity`: `0.18`
- `dependency_clarity`: `0.12`
- `verification_clarity`: `0.18`
- `consumer_context_clarity`: `0.12`

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
- `leaf_readiness` required for `executable_leaf`: `0.78`

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
- max decomposition candidates generated per node: `3`
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
- `leaf_readiness` required for `executable_leaf`: `0.84`

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
- max decomposition candidates generated per node: `3`
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
- critical assumptions remain unresolved

Likewise, a leaf may not be marked `executable_leaf` if:

- file scope is still ambiguous
- verification is nominal rather than actionable
- the consumer would still need to guess execution boundaries

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
