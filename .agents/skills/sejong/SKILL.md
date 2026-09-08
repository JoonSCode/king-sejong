---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for all-in-one research, decision support, formal planning, execution, verification, evidence records, rejected-option handling, or when continuing an active Sejong workflow that the user has not explicitly ended.
---

# Sejong

`sejong` is the lead router and synthesizer inside King Sejong. It is not a shim over another skill.

Always load `../../../docs/sejong/ROUTING_ENTRY.md` first and apply its
precedence, four route classes, continuity, completion, and gate checks. Do not
load the entire `../../../docs/sejong/ROUTER.md` merely to classify an ordinary
request. Load the selected court skill and only the detail contracts named by
the routing entry for the need that is actually present.

Preserve the user's requested terminal deliverable. Research, review,
comparison, recommendation, and proposal-only work may end with that result.
Settled authorized implementation goes through a compact execution contract to
Seungjeongwon. Materially unresolved intent, design, scope, authority, quality,
or acceptance goes through Uigwe first. A vague thought is valid Uigwe input;
joint discovery and a completed brief are Uigwe outputs.

Continue the active current goal without requiring another `$sejong` token or
repeating recorded approval. Do not silently make material user decisions.
Routine local implementation tactics remain autonomous inside approved scope.

For material Sejong self-modification, preserve the protected
`Jiphyeonjeon -> Uigwe -> Seungjeongwon` route. Reuse a settled approved
contract as decision and planning evidence without repeating debate,
interviews, or approval; reopen only for a consequential unresolved choice or
new counterevidence.

Treat `uigwe_promotion_required`, blocking ambiguity, and
`seungjeongwon_receipt_required` as current authority. Prior route history does
not satisfy a newly opened Uigwe gate, and outcome completion requires fresh
verification evidence or a real blocker.

Load `../../../docs/sejong/ROUTER.md` only for multi-surface or long-session
lifecycle, recursive goals, helper/council routing, worker selection, protected
self-modification detail, or failure recovery. Load
`../../../docs/sejong/HOOKS.md`, the context schemas,
`../../../docs/sejong/DISCIPLINE_GATES.md`, security/Sillok contracts, or
`../../../docs/sejong/REPO_CONTEXT.md` only when their routing-entry trigger is
present.
