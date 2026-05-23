---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for all-in-one research, decision support, formal planning, execution, verification, evidence records, rejected-option handling, or when continuing an active Sejong workflow that the user has not explicitly ended.
---

# Sejong

`sejong` is the all-in-one user-facing front door for broad research, decision support, planning triage, execution, verification, evidence recording, or direct action.

It is not a shim over another skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`.

## Routing

1. Load `../../../docs/sejong/ROUTER.md`.
2. Classify the request into the next useful Sejong surface.
3. Execute the selected surface when enough context is available; do not stop at only naming it.
4. If the user asked for an outcome rather than a single artifact, continue through downstream surfaces until the work is executed, verified, or blocked on a real missing decision.
5. Once invoked, keep follow-up turns inside the active Sejong workflow until the user explicitly exits Sejong or switches to another non-Sejong workflow; do not require the user to repeat `$sejong` on every turn.
6. For material changes to Sejong, Uigwe, Seungjeongwon, installer, validation, or artifact-storage behavior, use Jiphyeonjeon for unsettled decisions, Uigwe for planning and executable leaves, and Seungjeongwon for implementation and verification; reserve Sejong direct for non-behavioral typo, link, or formatting fixes.
7. Treat Korean court names as active user-facing surfaces:
   - `JangYeongsil` -> research, experiment, and evidence gathering
   - `Jiphyeonjeon` -> discussion, debate, option comparison, and decision support
   - `Uigwe` -> formal planning with Uigwe modes and artifacts
   - `Seungjeongwon` -> execution and verification through the native Seungjeongwon executor
   - `Sillok` -> evidence and promotion records
   - `Danjong` -> retired or rejected option semantics, never an execution surface

Canonical internal surface ids are `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`. Execution and verification are required behavior for `sejong-direct` and for any completed `seungjeongwon` path.

Boundary rule: use `JangYeongsil` when facts or evidence are unclear, `Jiphyeonjeon` when enough material exists but options need discussion, and `Uigwe` when the chosen direction should become a durable planning bundle. Preserve Uigwe live-session gates when routing there.

`Jiphyeonjeon` is an optional deliberation pass, not a required step in every Sejong chain. Use Codex native subagents only when independent research, option-review, implementation, or verification lanes would materially improve speed or confidence; the lead Sejong agent owns synthesis, final routing, and final verification.

For parallel Jiphyeonjeon, use bounded briefs from advocate, critic, specialist, operator, or risk-review lenses over the same evidence bundle; do not use subagent agreement as evidence or approval. Research, discussion, and planning may overlap only as preflight work: Uigwe gates and final packets remain lead/user-owned.

When using subagents, `.codex/prompts/{role}.md` is an optional repo-local overlay. If it is absent, use the Codex native role prompt and continue; do not treat missing overlays as a Sejong install failure.
