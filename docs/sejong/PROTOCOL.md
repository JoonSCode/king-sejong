# Uigwe Protocol

**Status:** Draft
**Full Name:** `Uigwe: Recursive Evidence-Guided Goal Planning Protocol`

## Purpose

`Uigwe` is a planning protocol for turning vague goals, partial briefs, or approved designs into evidence-backed handoff goal graphs.

It is designed to work across both:

- `greenfield` work, where intent and solution shape are still emerging
- `brownfield` work, where codebase reality, integration risk, and existing patterns matter

## Core Model

`Uigwe` has two layers.

- **Control plane:** `Recursive Gate Re-entry`
- **Data plane:** `Unified Evidence Graph Lite`

The control plane governs how planning progresses and when it must return to an earlier stage. The data plane stores the evolving planning state as linked goals, assumptions, decisions, risks, and evidence.

## Protocol Shape

`Uigwe` is a protocol, not a single fixed pipeline.

It can run in three entry modes:

- `full`: `deep-interview -> brainstorming -> decomposition`
- `design-to-plan`: `brainstorming -> decomposition`
- `decompose-only`: `decomposition`

The canonical stage ids remain `deep-interview`, `brainstorming`, and `decomposition`.
Machine-readable re-entry target ids are `local_reexploration`, `brainstorming`, `deep_interview`, and `human_review`.
The `deep_interview` re-entry target maps back to the `deep-interview` stage.
The preferred user-facing labels are `Intent Clarification`, `Design Exploration`, and `Executor Handoff Contract`.
Those labels refer to Uigwe's internal protocol stages, not separate required skills.
The machine-readable re-entry target ids above are escalation values, not stage ids.

Entry is not chosen only by user preference. It is gated by input readiness.

If the input does not satisfy the required contract for a later stage, Uigwe automatically re-enters the earlier stage needed to restore planning quality.

## Live Session Contract

In a live user session, Uigwe must behave as an interactive protocol rather than a one-shot bundle generator.

Rules:

- `deep-interview` requires actual questioning of the user when intent or boundaries are missing.
- `brainstorming` requires actual clarification with the user when material design ambiguities remain.
- Approval gates are real gates in live sessions. They may be marked `waived` only in explicitly non-interactive contexts such as offline artifact generation, offline evaluation, or when the user explicitly waives them.
- When a later stage discovers upstream ambiguity, Uigwe must re-enter the earlier stage and resume interaction with the user instead of silently filling the gap alone.
- General assistant defaults favoring autonomous progress do not override this protocol contract.
- When an ambiguity register is active, live stage clarification must reach `100%` readiness with no `open` ambiguity items before advancing, unless the user explicitly waives the remaining ambiguity.

## Ambiguity Register During Live Sessions

Sejong and Uigwe may record live clarification state in an external ambiguity
register that follows [ambiguity-register.schema.json](ambiguity-register.schema.json).

The active King Sejong context references this register through `artifact_refs`.
The register stores the user-facing stage label, readiness percentage, unclear
items, why each item matters, recommended options, free-response allowance,
user responses, status, and next required user action.

An ambiguity item with status `open` blocks stage completion. A `waived` item is
valid only when the user explicitly asks to skip, waive, or proceed despite that
ambiguity. Readiness percentages are progress signals; they do not permit
advancing while any item remains open.

## Context-Engineered Guardrail Planning

Uigwe should guide the model with compact, decision-relevant context and durable artifacts rather than a massive prompt.

For material planning or design decisions, Uigwe must make the decision boundary visible before downstream execution:

- source context the model should rely on
- user-owned decisions that require explicit choice or approval
- agent-owned low-risk implementation details that may be chosen autonomously
- 2-3 credible options when a choice materially changes scope, architecture, validation, cost, or risk
- the recommended option with trade-offs, rejected alternatives, and a free-response path
- success criteria, verification plan, and re-entry triggers

Plan-mode-style clarification is a useful live interaction pattern: gather context, expose options, ask for the missing decision, and then proceed. It is not the durable source of truth. The durable Uigwe result remains the approved packets, ambiguity-register state when used, and the Seungjeongwon handoff contract.

`PLANS.md`-style living plans may be useful for long-running implementation sessions, but they are optional executor-side aids. They must not replace canonical Uigwe artifacts or move Seungjeongwon's adaptive todo tree into the planning contract.

## Sejong Helper Calls During Uigwe

When Uigwe is running inside Sejong, it may call other court modes as bounded helpers without leaving the Uigwe protocol.

Uigwe may call JangYeongsil as an evidence helper during `deep-interview`, `brainstorming`, `decomposition`, or preflight checks when facts, examples, repo history, experiments, external constraints, or source evidence are missing. JangYeongsil returns `known`, `inferred`, `unknown`, source refs, confidence, and the decision it enables back to Uigwe. JangYeongsil research can run while Uigwe prepares artifact inventory, mode-readiness, or validation preflight, but blocking facts must be resolved before approval gates or packet finalization.

Uigwe may call Jiphyeonjeon as a decision-support helper during `deep-interview`, `brainstorming`, `decomposition`, or re-entry decisions when multiple perspectives would materially improve accuracy. Use it to sharpen the initial definition, compare design alternatives, challenge decomposition shape, assess whether execution feedback invalidates the design, or decide which option should be retired. Jiphyeonjeon returns the decision question, options, arguments, rejected options, risks, confidence, and next-surface recommendation back to Uigwe.

Helper calls return to Uigwe and do not approve gates or finalize canonical packets. They must not create competing `spec.md`, `rationale.md`, or `goal-tree.json` files, claim consensus as approval, waive live-session user approval, or override lead synthesis.

## Stage Contracts

### 1. Intent Clarification (`deep-interview`)

**Goal:** clarify intent and boundaries before design or decomposition.

Required outcomes:

- clear goal
- why this matters now
- explicit scope
- explicit non-goals
- explicit decision boundaries
- explicit constraints
- testable acceptance criteria

Artifact:

- `Intent Packet`

Approval model:

- interactive questioning during the stage
- one user approval gate after the stage summary is produced
- no default approval waiver in live sessions

### 2. Design Exploration (`brainstorming`)

**Goal:** compare approaches, select a design direction, and keep viable alternatives visible.

Required outcomes:

- problem framing
- 2-3 credible approaches
- selected approach
- trade-offs
- key design decisions
- assumptions and risks
- validation plan

Artifact:

- `Design Packet`

Approval model:

- interactive clarification during the stage
- one user approval gate after the design summary is produced
- no default approval waiver in live sessions

### 3. Executor Handoff Contract (`decomposition`)

**Goal:** turn the selected design into a bounded executor contract without losing rationale.

Required outcomes:

- selected handoff plan
- retained alternatives
- handoff leaves
- dependency graph
- risk summary
- executor-ready handoff data
- execution guardrails for the executor

Artifacts:

- `Plan Packet`
- `spec.md`
- `rationale.md`
- `goal-tree.json`

Before handoff to Seungjeongwon, Uigwe must define the execution guardrails the executor is not allowed to silently change:

- `goal`
- `non_goals`
- `success_criteria`
- `verification_plan`
- `must_preserve` behaviors or contracts
- `acceptable_tradeoffs`
- `reentry_triggers`
- handoff leaves with done criteria, scope boundaries, dependencies, verification expectations, and re-entry triggers

This is intentionally similar to test-first development: the success bar and verification method are set before implementation begins. Seungjeongwon may adapt tactics during decomposition and execution, but it must not change the approved goal, non-goals, success criteria, must-preserve behavior, or verification bar without Uigwe re-entry or human review.

Uigwe handoff leaves are not final implementation todos. They are bounded objectives that are clear enough for Seungjeongwon to begin executor-side decomposition. Seungjeongwon owns the later todo listup, todo verification, subtodo decomposition, actionable-leaf detection, execution attempts, verification, and retry ledger.

### Uigwe To Seungjeongwon Boundary

For outcome-completion work, `ready_for_handoff=true` means the work is ready to enter Seungjeongwon, not ready for ordinary direct edits. Uigwe defines the execution contract; Seungjeongwon performs actionable decomposition, implementation, verification, and execution feedback.

Uigwe must not mark a goal-bearing bundle complete by assuming the executor step away. The handoff is complete only when the next surface is explicitly Seungjeongwon, or when the user explicitly converts the request to plan-only/no-execution output before handoff.

Sejong direct may handle small exact non-goal operations, but it must not replace Seungjeongwon for a handoff-ready Uigwe contract.

### Implicit Native Goal Handoff

When a live Sejong/Uigwe workflow is goal-bearing and reaches `ready_for_handoff=true`, the default handoff to Seungjeongwon is `implicit native goal handoff` when the host runtime exposes native goal support.

This does not require the user to type `/goal` separately. The user's request for Sejong/Uigwe to carry an outcome through execution is treated as delegation for goal-backed execution once Uigwe has produced a stable handoff contract.

Implicit native goal handoff is allowed only when all of these are true:

- the original request is outcome-completion work, not research-only, advice-only, plan-only, or no-execution work
- live ambiguity is closed or explicitly waived
- the bundle is handoff-ready with success criteria, verification plan, and re-entry triggers
- the next surface is Seungjeongwon execution, not Sejong direct maintenance
- the host runtime provides a native goal surface

Uigwe prepares the goal payload at the handoff boundary:

- objective tied to the approved Uigwe contract
- completion criteria
- verification evidence requirements
- blocker and re-entry policy
- source refs for the selected bundle or handoff leaves

The native goal payload must stay broad. It must not contain the executor's full todo tree, speculative implementation steps, or first-attempt tactics. Seungjeongwon owns those details through its adaptive todo decomposition, visible execution board, attempt ledger, and verification loop.

If native goal support is unavailable, Seungjeongwon still runs the same execution loop and records `native_goal_unavailable` in execution feedback when machine-readable feedback is produced.

## Readiness-Gated Entry

A stage may be skipped only when the incoming packet is strong enough.

- the Uigwe `Design Exploration` (`brainstorming`) phase may start when an `Intent Packet` is present or equivalent requirements are already available
- the Uigwe `Executor Handoff Contract` (`decomposition`) phase may start when a `Design Packet` is present or equivalent approved design material already exists

If executor handoff contract generation detects unresolved design ambiguity, Uigwe re-enters the `Design Exploration` (`brainstorming`) phase.

If design exploration or executor handoff contract generation detects unresolved intent ambiguity, Uigwe re-enters the `Intent Clarification` (`deep-interview`) phase.

In live sessions, that re-entry means Uigwe returns to asking the user the missing questions before producing downstream artifacts.

## Handoff Decomposition Engine

The decomposition engine uses recursive `select -> review -> reselect` descent until each branch reaches handoff-leaf readiness.

At each expandable node, Uigwe treats that node as a local objective. It selects candidate child objectives that could satisfy the parent objective, reviews those candidates against gates and scoring, reselects when the candidate set is weak or invalid, and then repeats the same loop for each selected child.

For nested goals, keep one top-level Uigwe bundle and represent recursive work in `goal-tree.json` by default. A child objective may use JangYeongsil for missing evidence or Jiphyeonjeon for option judgment, but those helper results return to the active Uigwe node before that node becomes a handoff leaf.

Create a separate Uigwe bundle for a child objective only when it has its own durable goal, non-goals, success criteria, approval boundary, and verification bar independent of the parent bundle.

`gated beam BFS + backtracking` is the implementation shape for this loop.

### Recursive Selection Loop

For each expandable node:

1. Define the node objective from the parent goal, selected design, constraints, non-goals, and expected done state.
2. Select `2-3` candidate child objective sets that could satisfy that local objective.
3. Review each candidate set against hard gates before scoring.
4. Reselect locally when the candidate set is invalid, weak, duplicated, unverifiable, or misaligned with the parent objective.
5. Commit the selected child set when it satisfies the local objective, and preserve strong upper-level alternatives where useful.
6. Recurse into each selected child until it is either expanded again or marked `handoff_leaf`.

### Search Behavior

- expand breadth-first to stabilize top-level structure early
- generate `2-3` handoff decomposition candidates per expandable node
- reject invalid candidates through hard gates before scoring
- keep `1` selected candidate and preserve `2-3` strong alternatives at upper levels
- merge duplicated work into shared dependencies when appropriate, allowing a DAG rather than a strict tree

### Hard Gates

Candidates are rejected before scoring if they:

- violate `non_goals`
- violate `decision_boundaries`
- violate `constraints`
- conflict with the selected design direction
- cannot be verified
- claim to be a handoff leaf while still having ambiguous scope boundaries or outputs
- fail to satisfy the parent node objective

### Scoring Dimensions

Candidate ranking is based on a weighted combination of:

- `goal_contribution`
- `confidence`
- `verification_clarity`
- `dependency_simplicity`
- `cost`
- `risk`

The exact weights may differ by `greenfield` vs `brownfield` profile, but the shape stays the same.

Detailed defaults for scoring, readiness gates, and re-entry thresholds live in:

- `SCORING_AND_GATES.md`
- `policy.defaults.json`
- `policy.defaults.schema.json`

### Handoff Leaf Definition

A node becomes a handoff leaf when all of the following are explicit:

- what should be done
- why it matters
- what "done" means
- the affected file or responsibility scope boundary
- dependency prerequisites
- the verification expectation the executor must preserve
- the conditions that require local re-exploration, design re-entry, intent re-entry, or human review
- enough context for Seungjeongwon to decompose it into actionable work safely

A handoff leaf is not merely a small node. It is a bounded objective that is safe to hand to Seungjeongwon without further planning clarification.

An actionable leaf is different. It is a Seungjeongwon-owned execution unit produced after todo listup, todo verification, and subtodo decomposition. Uigwe does not need to predict the final actionable todo tree before execution starts.

### Leaf Stop Rule

Stop descending only when the selected node satisfies handoff-leaf readiness. If a node is small but still lacks done criteria, file or responsibility scope boundaries, dependency prerequisites, verification expectations, re-entry triggers, or executor context, it must be reselected, expanded again, or escalated through re-entry instead of being marked as a leaf.

## Planning Validation Workers

Uigwe may use bounded workers before gates, but their purpose is plan validation rather than open-ended debate. Suitable worker roles include:

- readiness checker
- risk checker
- scope checker
- dependency checker
- verification checker

These workers may inventory artifacts, scan for missing context, identify unverifiable handoff leaves, challenge dependency order, and report risks. They must not create competing canonical packets, finalize `spec.md`, finalize `rationale.md`, finalize `goal-tree.json`, approve gates, or overturn the selected design by consensus. If a worker finds evidence that invalidates the selected design, Uigwe re-enters the appropriate earlier stage instead of letting the worker decide.

## Re-entry Rules

`Uigwe` backtracks by severity.

### Local re-exploration

Use when:

- a subtree candidate is weak
- a better local alternative appears
- a dependency can be simplified without changing the chosen design
- Seungjeongwon actionable decomposition shows a handoff leaf needs tactical reshaping while preserving the approved goal, non-goals, success criteria, and verification bar

### Re-enter Design Exploration (`brainstorming`)

Use when:

- the chosen design no longer supports good decomposition
- dependency complexity grows beyond the intended architecture
- a retained alternative becomes clearly stronger than the selected approach
- Seungjeongwon decomposition or execution invalidates an architecture or design assumption rather than only a local implementation detail

### Re-enter Intent Clarification (`deep-interview`)

Use when:

- the goal itself is unstable
- `non_goals` are missing or contradicted
- `decision_boundaries` are missing or contradicted
- new evidence invalidates upstream scope assumptions
- execution evidence shows that the approved success criteria, non-goals, or user intent are incomplete or contradictory

## Internal State Model

The internal evidence graph is not the main user-facing artifact.

It is an internal planning state that links:

- `goal`
- `subgoal`
- `task`
- `constraint`
- `assumption`
- `alternative`
- `decision`
- `evidence`
- `risk`
- `approval`
- `question`
- `answer`

This graph preserves why a plan exists, not just what the plan says.

## Official Outputs

Human-facing outputs:

- `spec.md`
- `rationale.md`

Machine-facing output:

- `goal-tree.json`
- `goal-tree.schema.json`

Internal-only state:

- evidence graph state file

Storage policy:

- Uigwe's canonical outputs may be durable without being git-tracked
- default planning and evidence artifacts follow [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md)
- repository-tracked `spec.md`, `rationale.md`, `goal-tree.json`, and packet files require an explicit user promotion request

Validation references:

- `packets.schema.json`
- `goal-tree.schema.json`
- `scripts/validate_bundle.py`
- `scripts/validate_json_contracts.py`

## Goal Tree Contract

The `goal-tree.json` artifact is the canonical machine-facing output of Uigwe planning.

It must capture:

- the selected plan summary
- retained alternatives
- nodes
- dependency edges
- risk summary

Each node must include:

- identity
- type
- explanation
- acceptance criteria
- constraints
- assumptions
- alternatives
- score
- lifecycle status

Task nodes additionally require:

- done criteria
- file or responsibility scope
- verification checks
- risk level
- re-entry triggers
- optional consumer hints

The draft schema for this artifact lives in `goal-tree.schema.json`.

## Goal Tree Lifecycle

Node status is part of the protocol contract.

### Candidate states

- `candidate`
- `selected`
- `retained_alt`
- `invalidated`

### Handoff-readiness states

- `handoff_leaf`
- `blocked`

### Executor feedback states

- `actionable_leaf`
- `dispatched`
- `completed`

The intended transitions are:

- `candidate -> selected`
- `candidate -> retained_alt`
- `candidate -> invalidated`
- `selected -> handoff_leaf`
- `selected -> blocked`
- `selected -> invalidated`
- `handoff_leaf -> actionable_leaf`
- `handoff_leaf -> blocked`
- `actionable_leaf -> dispatched`
- `actionable_leaf -> blocked`
- `dispatched -> completed`
- `dispatched -> blocked`
- `blocked -> selected`
- `blocked -> invalidated`

Executor-facing states apply only after a handoff is initiated. `actionable_leaf` is produced by Seungjeongwon, not by Uigwe planning.

## Consumer Model

`Uigwe` is consumer-agnostic.

The default substantial execution path is `Seungjeongwon`. The lower-level `Codex subagent consumer` is still documented as a reference execution consumer, but it consumes actionable leaves prepared by an executor and should not be treated as Uigwe's planning output.

Consumers receive executor-prepared actionable leaves plus the relevant plan context and are expected to:

- consume actionable leaves only
- respect dependency ordering
- apply selective `critic` review for high-risk leaves
- apply `verifier` checks broadly
- report execution state back into the goal graph lifecycle

Reference consumer drafts:

- `CODEX_CONSUMER.md`
- `codex-consumer-feedback.schema.json`

## Executor Model

For substantial execution, Uigwe now distinguishes:

- **executor**: the higher-level post-planning handoff layer
- **consumer**: the lower-level leaf execution contract

Recommended default:

- `Seungjeongwon`

Reference docs:

- `EXECUTOR.md`
- `SEUNGJEONGWON_EXECUTOR.md`
- `TEAM_EXECUTOR.md` when `$team` or tmux-backed worker coordination is explicitly selected

Wrapper surface drafts:

- `WRAPPER.md`
- `wrapper.schema.json`

## Profiles

### Greenfield

Bias toward:

- intent clarity
- scope discipline
- alternative exploration
- risk shaping
- wider early exploration beam
- later convergence only after sufficient design confidence

### Brownfield

Bias toward:

- codebase grounding
- compatibility with existing patterns
- integration risk
- verification rigor
- file and ownership scope clarity
- narrower early beam with stricter handoff-leaf requirements

## Lifecycle Summary

1. detect the strongest valid entry point
2. run the current stage until its packet is ready
3. collect approval if the stage requires it
4. move forward into the next stage
5. if contradiction or instability appears, re-enter the appropriate earlier stage
6. stop when a valid `Plan Packet` and official outputs exist

## Non-Goals

`Uigwe` does not try to:

- replace execution systems
- force all tasks through the full `1 -> 2 -> 3` pipeline
- eliminate human judgment
- preserve every rejected branch forever

## Draft Open Questions

These items are intentionally left open for later refinement:

- exact score weights by profile
- exact persistence format for internal evidence graph state
- default threshold for escalating from local backtracking to stage re-entry
- standardized consumer feedback contract beyond the first Codex implementation
