# JangYeongsil Deep Research Profile

**Status:** Opt-in profile

## Purpose

Deep research is a JangYeongsil profile for evidence-heavy work where a normal
single-pass repo or web inspection is too shallow.

Use it when the user asks for deep research, broad comparison, source-backed
strategy, or a decision that needs several independent evidence lanes.

It is not a new court mode. It does not approve Uigwe gates, choose final
strategy by worker vote, or replace Sejong lead synthesis.

When exposed as a user-facing specialist UX, deep research uses the
`bounded-specialist-evidence` profile from [UX_PROFILES.md](UX_PROFILES.md).
That profile changes evidence depth and presentation only; it does not change
authority.

## Activation

Activate this profile only when one of these is true:

- the user explicitly asks for deep research, ultra research, or similar
  evidence depth
- Sejong, Uigwe, or Jiphyeonjeon needs multiple independent evidence lanes
  before a decision
- prior evidence is thin, stale, contradictory, or too narrow for the requested
  decision

For research-only prompts, the result can stop at a JangYeongsil evidence note.
For decision, planning, or execution prompts, the result must return a
decision-ready evidence summary and the next surface, usually `jiphyeonjeon` or
`uigwe`.

## Required Shape

The Sejong lead or calling court mode defines:

- decision question
- scope boundaries and non-goals
- independent research axes
- source priority and freshness requirements
- stop condition for each lane
- allowed outputs
- required confidence, unknowns, and verification refs

Each research lane returns:

- `known`: sourced facts
- `inferred`: conclusions that follow from the facts
- `unknown`: missing, stale, disputed, or unverified claims
- `source_refs`: files, commands, official docs, URLs, or reviewed artifacts
- `decision_enabled`: what this evidence now allows the lead to decide

The final fan-in separates:

- facts that all lanes support
- facts supported by one lane only
- contradictions and how they were handled
- discarded claims
- remaining unknowns
- recommended next surface

## Worker Backends

Use Codex native subagents, host-native team messaging, TeamExecutor, shell
commands, web search, local logs, or manual source inspection only when the axes
are genuinely independent. Workers are evidence collectors, not voters.

Do not copy external workflow state models into the repository. Runtime
artifacts belong under
`${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user explicitly asks
to promote a tracked artifact.

## Workflow-Run Evidence

When the deep research profile evaluates a reusable workflow tactic, many-agent
backend, or promoted research template, record a `workflow-run` artifact. That
artifact is evidence only. See [WORKFLOW_RUN.md](WORKFLOW_RUN.md).

The promoted example
`docs/sejong/examples/workflow-run-corpus/deep-research-codex-subagents/workflow-run.json`
shows the evidence shape for a Codex-native deep-research backend.

## Output Contract

Return a compact note in this order:

1. Decision question.
2. Research axes covered.
3. Known facts with source refs.
4. Inferred conclusions.
5. Unknowns and freshness limits.
6. Contradictions or discarded claims.
7. Recommendation and next surface.

If the user asked to proceed after the recommendation, route through Uigwe
before execution unless the work is a small exact direct action.
