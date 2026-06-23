# UX Profiles

**Status:** Draft presentation contract

## Purpose

UX profiles let King Sejong feel lighter or more task-specific without creating
new court modes.

They are presentation and helper-selection overlays. They do not own routing,
planning approval, execution authority, or completion claims.

Profiles are not court modes.

Use this document when adding LazyCodex-style default/detail/specialist UX to
Sejong.

## Non-Goals

- Do not add new court surfaces.
- Do not replace Uigwe stages with a `detail` mode.
- Do not let specialist output approve Uigwe gates.
- Do not let diagnostics imply execution permission.
- Do not let status HUDs imply completion.
- Do not store runtime state outside the Sejong artifact root.

## Profiles

### `compact/default`

Use when the user wants the work handled with minimal ceremony.

Behavior:

- Sejong still chooses the real court surface.
- The user-facing report stays short.
- Low-risk assumptions may be stated once and acted on.
- Blocking ambiguity, protected paths, external actions, and irreversible work
  still trigger Uigwe or user clarification.

This profile is not `sejong-direct`. It can still route to JangYeongsil,
Jiphyeonjeon, Uigwe, or Seungjeongwon when the task requires it.

### `expanded/detail`

Use when the user asks for careful reasoning, research, debate, why, planning,
or when task risk is high enough that the path should be visible.

Behavior:

- Show evidence, assumptions, rejected options, risks, and next surface.
- Make Uigwe readiness and approval boundaries explicit when planning is active.
- Make Seungjeongwon verification evidence explicit when execution is active.

This profile does not create canonical Uigwe artifacts. Only Uigwe writes or
approves the planning contract.

### `bounded-specialist-evidence`

Use when a task-specific lens would materially improve evidence quality.

Examples:

- deep research
- frontend review
- code review
- release readiness
- doctor diagnostics
- repo-context candidate review
- code-intelligence inspection

Behavior:

- The specialist returns bounded evidence, diagnostics, or a candidate note.
- The output names an `owner_surface` and `next_surface`.
- The output lists forbidden claims.
- Sejong lead synthesizes the result.

Specialists do not vote, approve gates, choose final strategy, or verify final
completion by themselves.

## Activation Rules

Profiles are selected by communication and evidence needs, not by authority.

Use `compact/default` when:

- the task is clear
- risk is low
- verification is obvious
- the user asks to proceed without ceremony

Use `expanded/detail` when:

- the request says `compare`, `why`, `deep research`, `debate`, `plan`,
  `전부`, `끝까지`, `세심하게`, or equivalent wording
- the task touches protected Sejong contracts, installer, hooks, schemas,
  security, release, or irreversible external actions
- ambiguity affects scope, architecture, validation, cost, or user-visible
  behavior

Use `bounded-specialist-evidence` when:

- a specialist lens has a clear evidence scope
- the output can be bounded
- final synthesis remains with Sejong

## Output Contract

Any adapter or specialist output that claims to use a UX profile must include:

- `profile`
- `owner_surface`
- `next_surface`
- `claim_type`
- `known`
- `inferred`
- `unknown`
- `forbidden_claims`

Required forbidden claims:

- `no_gate_approval`
- `no_execution_approval`
- `no_completion_claim`

Allowed `claim_type` values:

- `presentation`
- `evidence`
- `diagnostic`
- `status`
- `handoff_input`

## Authority Boundary

Profiles may change:

- how much context is shown
- whether a specialist evidence lane is used
- how assumptions and risks are summarized
- whether the user sees a compact or expanded report

Profiles may not change:

- route authority
- Uigwe approval gates
- Seungjeongwon completion guardrails
- protected-path policy
- artifact storage policy
- worker authority boundaries

## Promotion Rule

Start new profile behavior in documentation, examples, or shadow
`workflow-run` evidence.

Promote route-affecting behavior only when outcome evidence shows that the
profile improves user clarity or result quality without gate bypass, authority
drift, or overplanning regressions.
