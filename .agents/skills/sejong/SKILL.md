---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for all-in-one research, decision support, formal planning, execution, verification, evidence records, or rejected-option handling.
---

# Sejong

`sejong` is the all-in-one user-facing front door for broad research, decision support, planning triage, execution, verification, evidence recording, or direct action.

It is not a shim over another skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`.

## Routing

1. Load `../../../docs/sejong/ROUTER.md`.
2. Classify the request into the next useful Sejong surface.
3. Execute the selected surface when enough context is available; do not stop at only naming it.
4. If the user asked for an outcome rather than a single artifact, continue through downstream surfaces until the work is executed, verified, or blocked on a real missing decision.
5. Treat Korean court names as active user-facing surfaces:
   - `JangYeongsil` -> research, experiment, and evidence gathering
   - `Jiphyeonjeon` -> discussion, debate, option comparison, and decision support
   - `Uigwe` -> formal planning with Uigwe modes and artifacts
   - `Seungjeongwon` -> execution and verification through the native Seungjeongwon executor
   - `Sillok` -> evidence and promotion records
   - `Danjong` -> retired or rejected option semantics, never an execution surface

Canonical internal surface ids are `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`. Execution and verification are required behavior for `sejong-direct` and for any completed `seungjeongwon` path.

Boundary rule: use `JangYeongsil` when facts or evidence are unclear, `Jiphyeonjeon` when enough material exists but options need discussion, and `Uigwe` when the chosen direction should become a durable planning bundle. Preserve Uigwe live-session gates when routing there.

`Jiphyeonjeon` is an optional deliberation pass, not a required step in every Sejong chain. Use Codex native subagents only when independent research, option-review, implementation, or verification lanes would materially improve speed or confidence; the lead Sejong agent owns synthesis, final routing, and final verification.
