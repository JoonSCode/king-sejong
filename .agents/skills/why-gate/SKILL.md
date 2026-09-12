---
name: why-gate
description: Challenge why/왜 and trade-offs in material product, technical, or team decisions.
---

# Why Gate

Why Gate is a rationale checkpoint. Use it to make important choices explain themselves: why this path, why not a simpler or stronger alternative, what cost is accepted, and what evidence would change the decision.

Use it when a user asks `why`, `why gate`, `ask me why`, `challenge my reasoning`,
`근거를 물어봐`, or `왜 그렇게 했는지`.

Do not interrogate every tiny step. Focus on decisions with risk, ambiguity, future maintenance cost, user impact, or weak evidence.

## Route

1. Identify the gate mode. Default to `self-audit` for your own work and `review` for a requested review. Use `interactive` when the user asks to answer questions or when a material user-owned decision is missing.
   - `interactive`: the user should answer the why question.
   - `self-audit`: Codex or a worker team should inspect its own reasoning.
   - `review`: use why questions to strengthen a code/design/product review.
   - `retrospective`: use why questions to turn experience into defensible narrative.
2. Select the smallest useful set of lenses.
   - Code lenses: data structure, abstraction, OOP boundaries, dependency ownership, readability, maintainability, performance, concurrency/lifecycle, testing, product behavior.
   - Product/app lenses: user goal, evidence, constraints, opportunity cost, metrics, risk, differentiation.
   - Experience lenses: role, decision ownership, tradeoff, impact, failure handling, learned principle.
3. Examine 1-3 high-value decisions at a time. In `self-audit` and `review`, answer from evidence; do not turn those modes into a user interview.
4. Capture the result as: `decision`, `reason`, `rejected alternatives`, `accepted cost`, `evidence or verification`, and `follow-up`.
5. Continue only while a nontrivial choice still lacks a usable reason, the user asks for more gates, or self-audit finds weak rationale.

## Interactive Choice Gates

Use only a question tool permitted in the current host mode. Tool visibility alone is insufficient: `request_user_input` may be limited to Plan mode. When an asynchronous question tool is allowed, continue independent approved work while the answer is pending.

- Ask the smallest useful question set, following the tool's current option schema.
- Put the recommended option first when appropriate and preserve the host's free-response path.
- Reuse earlier answers and approvals; do not ask the same decision again.
- If no permitted structured input tool exists, ask one concise plain-language question.
- For a required answer or approval, keep dependent work pending. A preselected option, silence, or elapsed time is not consent.
- For optional preferences, make a stated reasonable assumption after giving the user a reasonable chance to answer, and continue.

## Question Quality

Ask specific why questions, not generic "why did you do this?" questions.

Good questions compare a decision against a real alternative:

- "Why use this data structure instead of the simpler list/map shape?"
- "Why add this abstraction now instead of waiting for a second call site?"
- "Why not abstract this repeated logic?"
- "Why keep this dependency at the view/model/service boundary?"
- "Why is this lifecycle/concurrency owner the right one?"
- "Why is the test focused on this behavior instead of the integration path?"
- "Why is this product metric the one that should decide the next step?"

Use "why did you go further?" and "why did you stop here?" as paired pressure tests. A good gate can defend both overengineering risk and underengineering risk.

## Self-Audit

When Codex, Sejong, a worker team, or another agent should audit its own work:

1. List the top 3 decisions made or about to be made.
2. For each decision, answer the gate yourself using current evidence.
3. Mark each rationale as `strong`, `thin`, or `unknown`.
4. If any rationale is `thin`, revise the choice or gather evidence. Ask the user only when the missing decision belongs to them and materially changes the result.
5. If any rationale is `unknown`, do not claim the decision is settled.

Self-audit output should be concise:

```text
Why Gate self-audit
- Decision: ...
  Rationale: strong/thin/unknown
  Reason: ...
  Rejected alternative: ...
  Next action: ...
```

## Code Review

For code review, keep normal review discipline: findings come first when concrete defects exist. Use Why Gate to expose weak reasoning behind choices that may not be outright bugs.

Prioritize these review questions:

- Data structure: "Why this representation, and what access pattern proves it?"
- Abstraction: "Why abstract now, or why keep it concrete?"
- OOP boundary: "Why does this object own this responsibility?"
- Dependency: "Why is this dependency created, injected, or hidden here?"
- Readability: "Why is this shape easier to maintain than the direct version?"
- Lifecycle/concurrency: "Why is this the owner of cancellation, threading, or state mutation?"
- Testing: "Why does this test prove the behavior that can break?"

If the review finds no bug but rationale is weak, say that clearly:

```text
No concrete defect found. The main Why Gate is:
- Why keep this concrete instead of extracting a shared helper?
  Recommended answer: keep it concrete until a second real call site appears.
  Risk if wrong: duplicated behavior may drift later.
  Verification: revisit when the next call site lands.
```

## Exit Criteria

Stop the gate when one of these is true:

- Every selected nontrivial decision has a reason, rejected alternative, accepted cost, and verification path.
- The user chooses a recommended option or provides a free-form reason that is specific enough to defend.
- Self-audit revised or downgraded every weak claim.
- The remaining questions are preference-level and would slow the work without changing the decision.

Do not block execution just because more philosophical why questions are possible.

## Red Flags

- Asking many generic why questions instead of a few decision-specific gates.
- Treating the recommended option as mandatory.
- Forcing the user to write long prose when a choice answer is enough.
- Asking about abstractions only from one direction; challenge both premature abstraction and missing abstraction.
- Claiming a rationale is proven when it is only plausible.
- Letting the gate replace verification. Why Gate explains decisions; tests, builds, screenshots, source checks, or data verify outcomes.
