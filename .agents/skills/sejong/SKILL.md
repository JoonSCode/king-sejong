---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for research, decision support, planning triage, executor handoff, evidence records, rejected-option handling, or direct action routing.
---

# Sejong

`sejong` is the router: the user-facing front door for broad research, decision support, planning triage, executor handoff, or direct action routing.

It is not a shim over another skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`.

## Routing

1. Load `../../../docs/sejong/ROUTER.md`.
2. Classify the request into one canonical lane.
3. Execute the selected lane when enough context is available; do not stop at only naming the lane.
4. Treat Korean court names as aliases only:
   - `JangYeongsil` -> `research-brief`
   - `Jiphyeonjeon` -> `decision-brief`
   - `Seungjeongwon` -> `executor-handoff` through RalphExecutor
   - `Sillok` -> evidence and promotion records
   - `Danjong` -> retired or rejected option semantics, never an active lane

Canonical machine lanes are `research-brief`, `decision-brief`, `uigwe-plan`, `executor-handoff`, and `direct-action`.

Uigwe/의궤 remains the formal planning protocol and is used only when the routed lane selects formal planning. The canonical planning lane id is `uigwe-plan`; preserve Uigwe live-session gates when routing there.
