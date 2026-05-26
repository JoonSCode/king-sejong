---
name: jiphyeonjeon
description: Use when a user invokes Jiphyeonjeon/집현전 or when Sejong, Uigwe, JangYeongsil, or Seungjeongwon needs structured discussion, option comparison, adversarial review, council-style decision support, rejected-option handling, or bounded team challenge rounds.
---

# Jiphyeonjeon

`Jiphyeonjeon` is the King Sejong discussion and decision-support front door.

It is a thin court-mode skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`, with TeamExecutor behavior in `../../../docs/sejong/TEAM_EXECUTOR.md`.

## Workflow

1. Load only the relevant sections of `../../../docs/sejong/ROUTER.md`.
2. Frame the `decision_question`.
3. Identify serious options and the evidence bundle each option depends on.
4. Compare arguments for and against each serious option.
5. Record rejected options and reasons.
6. Recommend the next path with confidence, risks, and the next Sejong surface.

When the council is deciding from research that was gathered for a later plan, its recommendation is not the workflow conclusion. Return the selected option, rejected options, risks, and an Uigwe-ready input summary with `next_surface: uigwe`; do not route to Seungjeongwon or Sejong direct until Uigwe planning has run or the user explicitly cancels the promotion.

## Helper Use

Jiphyeonjeon may be called from Sejong, Uigwe, JangYeongsil, or Seungjeongwon as a helper call when multiple perspectives would materially improve accuracy.

Use it to sharpen a vague first Uigwe definition, compare design alternatives, challenge decomposition shape, assess whether execution feedback requires Uigwe re-entry, or decide which option should become Danjong.

Jiphyeonjeon does not approve Uigwe gates, finalize `spec.md`, finalize `rationale.md`, finalize `goal-tree.json`, claim worker consensus as approval, or replace lead-owned Sejong synthesis.

## Parallel Council

For substantial decisions, Jiphyeonjeon may use a bounded council:

1. Lead writes one shared council brief.
2. Workers produce independent first-round briefs from advocate, critic, specialist, operator, or risk-review lenses.
3. The lead opens at most one default challenge round for the strongest objections, or a `persuasion` round when workers should answer each other's objections before synthesis.
4. In a persuasion round, workers may try to change each other's position through bounded mailbox `claim`, `objection`, `question`, and `response` messages.
5. The lead closes persuasion when apparent convergence appears or after 30 minutes of deadlock.
6. The lead synthesizes the final recommendation, rejected options, risks, confidence, and next surface.

When official peer/team messaging is available in the host runtime, use it for bounded teammate messages and shared task state. Otherwise use `$team` / TeamExecutor mailbox messages. Peer messages are allowed only inside a bounded round and never become approval, final synthesis, or verification by themselves.
