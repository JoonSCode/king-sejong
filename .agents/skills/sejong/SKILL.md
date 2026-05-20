---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for all-in-one research, decision support, formal planning, execution, verification, evidence records, or rejected-option handling.
---

# Sejong

`sejong` is the all-in-one user-facing front door for broad research, decision support, planning triage, execution, verification, evidence recording, or direct action.

It is not a shim over another skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`.

## Routing

1. Load `../../../docs/sejong/ROUTER.md`.
2. Classify the request into the next useful canonical lane.
3. Execute the selected lane when enough context is available; do not stop at only naming the lane.
4. If the user asked for an outcome rather than a single artifact, continue through downstream lanes until the work is executed, verified, or blocked on a real missing decision.
5. Treat Korean court names as aliases only:
   - `JangYeongsil` -> `research-brief`
   - `Jiphyeonjeon` -> `decision-brief`
   - `Seungjeongwon` -> `executor-handoff` through RalphExecutor
   - `Sillok` -> evidence and promotion records
   - `Danjong` -> retired or rejected option semantics, never an active lane

Canonical machine lanes are `research-brief`, `decision-brief`, `uigwe-plan`, `executor-handoff`, and `direct-action`. Execution and verification are required behavior for `direct-action` and for any completed `executor-handoff` path.

Uigwe/의궤 remains the formal planning protocol and is used only when the routed lane selects formal planning. The canonical planning lane id is `uigwe-plan`; preserve Uigwe live-session gates when routing there.
