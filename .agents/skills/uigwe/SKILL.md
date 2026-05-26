---
name: uigwe
description: Use when a user explicitly invokes `uigwe`, `의궤`, or wants a vague goal, partial brief, approved design, or packet set turned into formal planning artifacts using `auto`, `full`, `design-to-plan`, or `decompose-only`.
---

# Uigwe

## Overview

`Uigwe` is the wrapper-facing skill for the formal planning protocol.

Use it to produce canonical Uigwe planning artifacts:

- `Intent Packet`
- `Design Packet`
- `Plan Packet`
- `spec.md`
- `rationale.md`
- `goal-tree.json`

This skill is a planning surface, not an execution surface.

If execution is requested after planning, hand off through the documented executor or consumer path instead of collapsing planning and execution together.

`deep-interview`, `brainstorming`, and `decomposition` are Uigwe's own protocol stage ids.
Machine-readable re-entry target ids are `local_reexploration`, `brainstorming`, `deep_interview`, and `human_review`.
User-facing labels are `Intent Clarification`, `Design Exploration`, and `Executor Handoff Contract`.
They are internal to this skill and do not require separately installed skills.

Sejong's formal planning surface is `uigwe`.

## Live Session Contract

In a live chat with a human user, Uigwe is an interactive protocol.

Mandatory rules:

- Do not silently complete `deep-interview` or `brainstorming` from one ambiguous brief.
- Ask targeted clarification questions in small batches and wait for the user's answers before advancing the stage.
- Do not generate an `Intent Packet` until intent, scope, non-goals, decision boundaries, constraints, and acceptance criteria are explicit enough to summarize back to the user.
- Do not generate a `Design Packet` until the design-stage ambiguities have been discussed with the user when they materially affect architecture, trade-offs, or validation.
- Do not mark an approval gate as `waived` in a live session unless the user explicitly says to skip approval.
- Offline artifact generation and other non-interactive evaluation contexts must be labeled explicitly. Only those contexts may auto-fill assumptions and waive approval gates by default.
- When an ambiguity register is active, do not advance the live stage until readiness is `100%` and there are no `open` ambiguity items, unless the user explicitly waives the remaining ambiguity.

These live-session rules override the general default to make reasonable assumptions and continue autonomously.

## User-Facing Stage Language

When speaking to a human user, explain the current stage in plain language instead of leading with packet names or internal stage ids.

Use the user's language. For Korean users, prefer:

- `Intent Clarification` -> `1단계: 기획 명확화`
- `Design Exploration` -> `2단계: 설계 명확화`
- `Executor Handoff Contract` -> `3단계: 실행 계약화`

Stage meanings should be explained like this:

- `1단계: 기획 명확화` = clarify what to build, why now, scope, non-goals, constraints, and success criteria
- `2단계: 설계 명확화` = clarify how to solve it, what alternatives exist, and what trade-offs matter
- `3단계: 실행 계약화` = turn the chosen design into a bounded Seungjeongwon handoff contract, dependencies, verification bar, and re-entry triggers
- Handoff-ready outcome-completion bundles implicitly hand off to goal-backed Seungjeongwon execution when host-native goal support is available; Uigwe prepares the broad objective and guardrails, while Seungjeongwon owns adaptive todo decomposition.

Progress reporting rules:

- Prefer readiness percentages such as `기획 준비도 68%` or `설계 준비도 74%` rather than raw ambiguity percentages
- Always pair the percentage with the main weak areas; do not present the number alone
- Treat the percentage as an approximate readiness signal derived from the current gates, not as a precise measurement
- If an ambiguity register is in use, show the current unclear items, recommended options, and a free-response path; readiness below `100%` means the stage is not complete.

Wording rules:

- Do not lead with `Intent Packet`, `Design Packet`, or `Plan Packet` unless the user already understands those artifact names or the discussion is specifically about artifacts
- Do not promise a fixed number of next questions; avoid wording like `설계 질문 2-3개`
- Instead, say `필요한 설계 질문들을 이어서 정리하겠습니다` or equivalent plain-language phrasing
- Approval prompts should say what is being confirmed and what the next stage is for

Recommended Korean approval phrasing:

- `지금까지 정리한 기획 내용을 이 기준으로 확정할까요?`
- `확정되면 다음으로는 "어떤 방식으로 풀지"를 정하기 위해 필요한 설계 질문들을 이어서 정리하겠습니다.`

## Suggested Invocation

Use `$uigwe` or `의궤` when you want to force this planning surface.

- Omit the mode to let the skill resolve `auto`
- Pass `full`, `design-to-plan`, or `decompose-only` only when you want to override auto mode
- Keep execution requests out of this skill; hand off through the executor or consumer path after planning

Examples:

- `$uigwe build a browser-based MVP for async interview practice`
- `$uigwe use the approved design at docs/specs/feature.md and decompose it`
- `$uigwe decompose-only this approved design into Seungjeongwon handoff leaves`
- `$uigwe design-to-plan this feature brief`

If the user does not specify a mode, treat the request as `auto`.

## Load Order

Read only what is needed, in this order:

1. `../../../docs/sejong/WRAPPER.md`
2. `../../../docs/sejong/PROTOCOL.md`
3. `../../../docs/sejong/EXECUTOR.md` when you need post-planning ownership or handoff semantics
4. `../../../docs/sejong/SEUNGJEONGWON_EXECUTOR.md` when the user wants implementation and verification after planning
5. `../../../docs/sejong/SCORING_AND_GATES.md` when you need numeric defaults or re-entry thresholds
6. `../../../docs/sejong/BUNDLE_VALIDATOR.md` when you need bundle validation or report shape
7. `../../../docs/sejong/VALIDATION.md` when you need planning benchmark targets, scorecards, or promotion gates
8. `../../../docs/sejong/SUMMARY_PROJECTION.md` when you need the human-facing summary projection
9. `../../../docs/sejong/CODEX_CONSUMER.md` only if direct consumer handoff is requested or executor/consumer boundary text is changing
10. `../../../docs/sejong/examples/README.md` only if you need reference examples

## When To Use

- The user wants a rigorous planning workflow rather than immediate implementation
- The user has a vague goal and wants to turn it into structured planning artifacts
- The user already has an approved design and wants executor handoff decomposition only
- The user wants one protocol that works for both `greenfield` and `brownfield`
- The user wants one standalone protocol that carries intent clarification, design exploration, and executor handoff decomposition as one system

## Do Not Use When

- The task is already a clear implementation task and planning would be performative
- The user explicitly wants direct execution right now
- The user only wants a lightweight opinion or quick comparison without artifact generation

## Inputs

Accept any of:

- a vague goal or brief
- an intent-equivalent requirements artifact
- an approved design artifact
- existing Uigwe packet paths
- existing Uigwe packet paths from earlier bundles

If the user does not specify mode, default to `auto`.

Accepted mode words:

- `auto`
- `full`
- `design-to-plan`
- `decompose-only`

## Mode Resolution

Resolve the entry point like this:

1. If a valid design artifact already exists, start with `decompose-only`
2. Else if intent is clear enough to skip interview, start with `design-to-plan`
3. Else start with `full`

If the chosen entry point proves too optimistic, re-enter the earlier stage required by readiness gates.

## Workflow

### `full`

1. Run the Uigwe `Intent Clarification` (`deep-interview`) phase
2. Ask the user the questions needed to resolve missing intent and boundary data before writing the packet
3. Produce `Intent Packet`
4. Get one approval on the interview summary
5. Run the Uigwe `Design Exploration` (`brainstorming`) phase
6. Ask the user the questions needed to resolve material design ambiguities before writing the packet
7. Produce `Design Packet`
8. Get one approval on the design summary
9. Run the Uigwe `Executor Handoff Contract` (`decomposition`) phase
10. Produce `Plan Packet`, `spec.md`, `rationale.md`, and `goal-tree.json`

### `design-to-plan`

1. Validate intent readiness
2. If intent readiness is not strong enough, re-enter `deep-interview` and ask the user the missing questions instead of inferring the missing boundaries alone
3. Run the Uigwe `Design Exploration` (`brainstorming`) phase
4. Ask the user the questions needed to resolve material design ambiguities before writing the packet
5. Produce `Design Packet`
6. Get one approval on the design summary
7. Run the Uigwe `Executor Handoff Contract` (`decomposition`) phase
8. Produce `Plan Packet`, `spec.md`, `rationale.md`, and `goal-tree.json`

### `decompose-only`

1. Validate design readiness
2. If the supplied design is missing a boundary the plan depends on, stop and ask the user or re-enter `brainstorming`; do not guess past the design contract
3. Run the Uigwe `Executor Handoff Contract` (`decomposition`) phase
4. Produce `Plan Packet`, `spec.md`, `rationale.md`, and `goal-tree.json`

## Sejong Helper Calls

Inside a Sejong workflow, Uigwe may call `JangYeongsil` as an evidence helper when facts, examples, repo history, experiments, or external constraints are missing. JangYeongsil returns `known`, `inferred`, `unknown`, source refs, confidence, and the decision it enables back to Uigwe.

Uigwe may call `Jiphyeonjeon` as a decision-support helper during `deep-interview`, `brainstorming`, `decomposition`, or re-entry decisions when multiple perspectives would materially improve accuracy. Jiphyeonjeon returns options, arguments, rejected options, risks, confidence, and a next-surface recommendation back to Uigwe.

Helper calls do not approve Uigwe gates, finalize `spec.md`, finalize `rationale.md`, finalize `goal-tree.json`, claim consensus, or replace user approval in live sessions. Uigwe remains responsible for formal packets, gate state, handoff leaves, and re-entry decisions.

## Decomposition Rules

- Treat each expandable node as a local objective: select candidate child objectives, review whether they satisfy the parent objective, reselect when they are weak or invalid, then recurse into selected children
- For nested goals, keep one top-level Uigwe bundle and recursive `goal-tree.json` by default; create a separate Uigwe bundle for a child objective only when it has its own durable goal, non-goals, success criteria, approval boundary, and verification bar independent of the parent
- Use breadth-first decomposition with hard gates before scoring
- Preserve `1` selected branch and keep `2-3` strong alternatives at upper levels
- Allow shared dependencies when the structure is naturally a DAG
- Mark a node `handoff_leaf` only when objective, done criteria, scope boundary, dependencies, verification expectation, and re-entry triggers are all explicit
- Before handing off to Seungjeongwon, define goal, non-goals, success criteria, verification plan, must-preserve behaviors, acceptable tradeoffs, re-entry triggers, and handoff leaves
- Use Uigwe workers only for plan validation such as readiness, risk, scope, dependency, and verification checks; do not use worker consensus to approve gates or reopen the selected direction

Uigwe does not produce the final implementation todo list. Seungjeongwon owns todo listup, todo verification, subtodo decomposition, actionable-leaf readiness, execution attempts, verification, evidence capture, and retry ledger.

If decomposition becomes unstable:

- retry locally first when the issue is subtree-local
- re-enter the Uigwe `Design Exploration` (`brainstorming`) phase when the selected design path is failing
- re-enter the Uigwe `Intent Clarification` (`deep-interview`) phase when intent, scope, non-goals, or decision boundaries are unstable
- treat Seungjeongwon decomposition and execution feedback as evidence: local implementation mismatches may trigger local re-exploration, but broken handoff leaves, design assumptions, or success criteria trigger Uigwe re-entry

Use the numeric defaults in `../../../docs/sejong/SCORING_AND_GATES.md` and `../../../docs/sejong/policy.defaults.json` unless the user explicitly overrides them.

## Outputs

The canonical result of this skill is a Uigwe artifact bundle:

- `Intent Packet` when generated
- `Design Packet` when generated
- `Plan Packet`
- `spec.md`
- `rationale.md`
- `goal-tree.json`

Do not treat prose summaries alone as completion.

When the task is to improve Uigwe itself, keep the public skill surface small:

- update the relevant contract doc first
- update schemas and examples that depend on that contract
- use `../../../docs/sejong/VALIDATION.md` for planning-method changes, instruction-surface regression checks, and promotion gates
- run `python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets` for Uigwe or Sejong instruction-surface changes
- validate JSON contracts and example bundles before claiming the change is ready
- keep private evaluation corpora and score histories outside the installed package

## Optional Execution Handoff

If the user explicitly wants execution after planning:

1. Finish planning first
2. Confirm the plan bundle is handoff-ready and safe to pass to Seungjeongwon
3. Prefer Seungjeongwon for substantial work inside King Sejong
4. Let Seungjeongwon decompose dependency-ready handoff leaves into actionable work, then execute and verify before reporting completion
5. Emit execution feedback with changed files, verification evidence, blockers, and recommended Uigwe re-entry if needed
6. Follow `../../../docs/sejong/CODEX_CONSUMER.md` only when a lower-level direct consumer path is explicitly desired

Do not invent a custom execution lane inside this skill.

## Done Criteria

- The correct entry mode was chosen or corrected by readiness-gated re-entry
- Required packets for the traversed stages exist
- `spec.md`, `rationale.md`, and `goal-tree.json` exist
- `goal-tree.json` is valid against the Uigwe goal-tree contract
- Planning contradictions were either resolved or escalated explicitly
- Seungjeongwon handoff leaves preserve the approved goal, non-goals, success criteria, verification bar, must-preserve behaviors, and re-entry triggers

## Failure Handling

Stop and surface a blocker when:

- supplied artifacts materially disagree
- readiness gates fail and the user rejects re-entry
- a required boundary decision is missing
- decomposition cannot produce handoff leaves without guessing

In a live session, unresolved ambiguity is a reason to ask the user and pause the stage, not a reason to auto-complete the stage with hidden assumptions.

Recommended escalation targets:

These target names are Uigwe machine-readable re-entry ids, not protocol stage ids.

- `local_reexploration`
- `brainstorming`
- `deep_interview`
- `human_review`
