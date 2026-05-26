# King Sejong Role Separation

**Status:** Draft

## Purpose

This document is the durable role-boundary reference for King Sejong maintenance.

The court names are modes under a Sejong lead, not independent authorities. Workers and subagents may contribute evidence, arguments, implementation slices, or verification observations, but the Sejong lead owns synthesis and final routing.

## Roles

| Role | Owns | Must Not Own |
| --- | --- | --- |
| `Sejong` | front-door routing, synthesis, final route decision, completion responsibility | duplicating Uigwe packet rules or treating worker agreement as approval |
| `JangYeongsil` | evidence gathering, experiments, repo/source inspection, known/inferred/unknown separation | strategy finalization, Uigwe gate approval, execution completion |
| `Jiphyeonjeon` | option comparison, adversarial discussion, persuasion rounds, rejected-option reasoning | voting as final decision, Uigwe gate approval, final verification |
| `Uigwe` | ambiguity closure, idea/design clarification, success criteria, verification bar, handoff leaves | implementation attempts or silent success redefinition |
| `Seungjeongwon` | todo verification, recursive actionable decomposition, execution, retry, verification evidence, feedback | weakening Uigwe criteria or changing approved scope without re-entry |
| `Sillok` | evidence and decision records | making new decisions without the lead route |
| `Danjong` | rejected or retired option semantics | execution |
| `TeamExecutor worker` | bounded mailbox message, evidence, perspective, implementation slice, verification observation | final synthesis, majority decision, gate approval, final verification |

## Default Flow

Use this when the user asks for a goal rather than a one-shot answer:

```text
JangYeongsil when evidence is missing
-> Jiphyeonjeon when serious options need argument
-> Uigwe when the selected direction needs a durable plan
-> Seungjeongwon when the plan or clear scope should be executed
-> Sillok when evidence should be recorded
```

Do not force every request through every role. Small exact tasks can use Sejong direct. Research-only requests can stop at JangYeongsil. Advice-only requests can stop at Jiphyeonjeon until the user asks to concretize or execute the recommendation.

## Uigwe Clarification Duty

Uigwe must close uncertainty before execution:

- idea clarity first
- then design clarity
- then success criteria and pass/fail methods for Seungjeongwon
- then handoff leaves

Clarification should not be a bare question list. Provide recommended options plus a free-response path. Keep asking only while the ambiguity materially changes scope, design, success criteria, verification, or risk.

## Seungjeongwon Execution Duty

Seungjeongwon accepts a clear direct scope or Uigwe handoff, then recursively decomposes until actionable leaves exist:

```text
todo listup
-> todo necessity and contribution check
-> verification feasibility check
-> subtodo decomposition when not actionable
-> implementation
-> verification
-> attempt ledger
-> retry or re-entry
```

If verification fails, Seungjeongwon records the attempt and chooses the next hypothesis. If the approved goal, success criteria, design, or verification bar is wrong, it returns to Uigwe instead of locally redefining success.

## Jiphyeonjeon Persuasion

Jiphyeonjeon is optimized for parallel perspectives and persuasion, not one-pass independent summaries.

For substantial decisions:

1. Lead writes one shared council brief.
2. Workers produce independent first-round positions.
3. Workers may challenge and answer each other through bounded mailbox messages.
4. The lead closes the round when apparent convergence appears or after 30 minutes of deadlock.
5. The lead synthesizes the final decision note.

This is not a vote. Agreement is signal, not authority.

## JangYeongsil Research

JangYeongsil can be spawned as one or many bounded research lanes. Multiple lanes are useful when evidence sources are independent, such as external docs, repo history, market examples, code experiments, or benchmark results.

Each lane returns:

- `known`
- `inferred`
- `unknown`
- confidence
- source refs
- the decision or verification it enables

## Worker Communication

When TeamExecutor is used, mailbox messages must use the versioned `send-message` / `receive-messages` envelope. Raw mailbox appends are compatibility-only.

Workers may persuade, object, ask questions, answer by `target_message_id`, and cite evidence. They must not claim final authority.

## Maintenance Rule

When a future change blurs these boundaries, update this document, the relevant skill front door, tests, and benchmark checks together.
