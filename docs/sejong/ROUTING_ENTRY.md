# Sejong Routing Entry

**Status:** Draft

## Purpose

This is the canonical first read for Sejong route selection. It contains the
high-frequency precedence rules, the four route classes, and the guards that
must survive selective loading. Read [ROUTER.md](ROUTER.md) only when the
selected route needs its detailed lifecycle, helper, council, or failure rules.

The entry chooses the next useful court surface. It does not replace the
selected court skill or its detailed contract.

## Precedence And Continuity

Apply these rules in order:

1. Follow higher-priority instructions and the user's explicit scope,
   authorization, requested deliverable, and explicit court invocation.
2. Continue an active Sejong workflow for the same current goal until the user
   exits it, completes or replaces the goal, or switches to another workflow.
   Reuse recorded decisions and approvals. Do not invent a new goal or ask for
   the same approval again merely because time passed or context was compacted.
3. Treat a named court surface as an active routing request. Enter
   JangYeongsil for evidence, Jiphyeonjeon for judgment, Uigwe for joint
   intent/design discovery or formal planning, and Seungjeongwon for authorized
   execution and verification.
4. For material changes to Sejong, Uigwe, Seungjeongwon, installer,
   validation, or artifact-storage behavior, preserve the protected
   `Jiphyeonjeon -> Uigwe -> Seungjeongwon` route. A settled approved contract
   may satisfy the decision and planning evidence without repeating debate,
   interviews, or approval. Reopen only a consequential unresolved choice or
   new counterevidence. Narrow non-behavioral typo, link, and formatting fixes
   may remain Sejong direct.
5. Pending gates are current authority. A new `uigwe_promotion_required` gate
   remains unresolved even when older route history contains Uigwe. Clear it
   only when the current required Uigwe entry is recorded or the user changes
   the scope. Preserve `seungjeongwon_receipt_required` until the required
   Seungjeongwon entry and valid execution receipt are recorded. Do not silently
   decide a material goal, design, scope, authority, quality, or acceptance
   boundary to bypass either gate.

Routine local implementation tactics are autonomous inside the approved scope
and constraints.

## Conditional Agent Company Reply Continuity

Only during an explicitly active Agent Company session, every ordinary prose
final reply begins by identifying the responder and the workers whose results
it actually uses, with each worker's short responsibility. A direct reply has
no worker participant. Keep this on follow-ups: a prior status update, skill
use, planned worker, or unconsumed worker output is not participation evidence.
Do not insert it into strict JSON, code-only, or other exact-format output;
give it separately only when prose is allowed. This pointer does not activate
Agent Company for ordinary Sejong work.

## Four Route Classes

| Request state | Route | Terminal condition |
| --- | --- | --- |
| Research, review, comparison, recommendation, or proposal only | Use JangYeongsil when evidence is missing, Jiphyeonjeon when options need judgment, or Sejong direct for a small exact answer. | Stop with the requested evidence or advice deliverable. Do not create an implementation or Uigwe obligation. |
| Settled, authorized implementation | Connect the current request, prior approval, scope, acceptance criteria, and verification bar in a compact execution contract, then enter Seungjeongwon. | Continue through execution and fresh verification, or record a real blocker. Do not add synthetic Uigwe ceremony. |
| Authorized implementation with a material unresolved boundary | Enter Uigwe to discover and settle the goal, design, scope, authority, quality, or acceptance boundary together; then enter Seungjeongwon when the outcome contract is handoff-ready. | Stop only for a required user choice, a real blocker, or verified execution. |
| Explicit Uigwe, joint discovery, or formal planning | Enter Uigwe in the appropriate mode. A vague thought is valid input; Uigwe asks informed questions, explains reasons and alternatives, accepts free answers, and produces the completed brief as output. | Stop at the plan when planning is the requested deliverable, or hand off authorized execution to Seungjeongwon. |

Research and debate helpers may support any route without gaining approval or
completion authority. Do not merely bounce generic goal or done questions back
to the user. Ask only for consequential missing choices and continue independent
authorized work while a dependent answer is pending.

## Completion And Gate Check

Before action or completion, check the current goal, requested terminal
deliverable, authority, and pending gates:

- Terminal research or advice is complete when that requested deliverable is
  supported and delivered. It does not imply implementation.
- Outcome work continues to verified execution or a real blocker. A clear
  request alone does not make goal-bearing implementation Sejong direct.
- Blocking ambiguity prevents dependent work. Optional preferences do not.
- A pending Uigwe gate represents the current unresolved boundary; historical
  membership in a route sequence does not satisfy it.
- A pending Seungjeongwon receipt gate prevents write-like execution until the
  required entry and receipt exist. Create or reuse a native goal only when
  current host tool conditions permit it and the user explicitly requested a
  goal; ordinary outcome authorization alone is insufficient.
- Never claim completion from worker agreement, chat progress, a queued action,
  or an unverified artifact.

## Selective Contract Loading

After selecting a route, load only the contracts needed to perform it:

| Need | Load |
| --- | --- |
| Bounded evidence | the JangYeongsil skill; add [DEEP_RESEARCH.md](DEEP_RESEARCH.md) only for broad, multi-axis research |
| Option comparison or challenge | the Jiphyeonjeon skill; add the relevant [ROUTER.md](ROUTER.md) council section and [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) only when a bounded council or worker backend is useful |
| Intent/design discovery or formal planning | the Uigwe skill, then [WRAPPER.md](WRAPPER.md) and [PROTOCOL.md](PROTOCOL.md) as that skill directs; add [AMBIGUITY_REGISTER.md](AMBIGUITY_REGISTER.md) only for durable live ambiguity state |
| Authorized execution and verification | the Seungjeongwon skill and [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md); add bundle validation only when a bundle is present |
| Multi-surface chains, long-session lifecycle, recursive goals, helper routing, worker selection, protected self-modification detail, or routing failure recovery | the relevant sections of [ROUTER.md](ROUTER.md) |
| Active hook, route-sequence, ambiguity, receipt, or completion gate | [HOOKS.md](HOOKS.md), the relevant context schema, and [DISCIPLINE_GATES.md](DISCIPLINE_GATES.md) as needed |
| Security-sensitive evidence or external action | [SECURITY.md](SECURITY.md) and [SILLOK_TRACE.md](SILLOK_TRACE.md) |
| Repository instruction initialization or refresh | [REPO_CONTEXT.md](REPO_CONTEXT.md) |

Do not load the entire Router merely to classify an ordinary request. Load a
detail contract when its trigger is present, and keep the entry's route and
authority decisions unchanged while applying that detail.
