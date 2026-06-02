---
name: why-gate
description: "Use when Codex should force explicit rationale before or after decisions: code review, implementation planning, architecture or abstraction choices, data structure choices, dependency ownership, maintainability tradeoffs, product/app analysis, experience writeups, retrospectives, or agent/team self-audits. Use when the user asks \"why\", \"why gate\", \"ask me why\", \"challenge my reasoning\", \"근거를 물어봐\", \"왜 그렇게 했는지\", or wants choice-based rationale prompts with recommended options plus free-form answers."
---

# Why Gate

Why Gate is a rationale checkpoint. Use it to make important choices explain themselves: why this path, why not a simpler or stronger alternative, what cost is accepted, and what evidence would change the decision.

Do not interrogate every tiny step. Focus on decisions with risk, ambiguity, future maintenance cost, user impact, or weak evidence.

## Route

1. Identify the gate mode.
   - `interactive`: the user should answer the why question.
   - `self-audit`: Codex or a worker team should inspect its own reasoning.
   - `review`: use why questions to strengthen a code/design/product review.
   - `retrospective`: use why questions to turn experience into defensible narrative.
2. Select the smallest useful set of lenses.
   - Code lenses: data structure, abstraction, OOP boundaries, dependency ownership, readability, maintainability, performance, concurrency/lifecycle, testing, product behavior.
   - Product/app lenses: user goal, evidence, constraints, opportunity cost, metrics, risk, differentiation.
   - Experience lenses: role, decision ownership, tradeoff, impact, failure handling, learned principle.
3. Ask 1-3 high-value why gates at a time.
4. Capture the result as: `decision`, `reason`, `rejected alternatives`, `accepted cost`, `evidence or verification`, and `follow-up`.
5. Continue only while a nontrivial choice still lacks a usable reason, the user asks for more gates, or self-audit finds weak rationale.

## Interactive Choice Gates

When a choice UI such as `request_user_input` is available in the current runtime, use it for interactive Why Gate questions:

- Ask 1-3 short questions at a time.
- Give 2-3 mutually exclusive options.
- Put the recommended option first and suffix its label with `(Recommended)`.
- Do not add an `Other` option; the UI provides a free-form path.
- Make each option description state the tradeoff or consequence.
- Stop after asking and wait for the user's answer.

When that UI is unavailable, present the same structure in text:

```text
Why Gate
Q: Why did you choose this data structure here?

A. Keep it simple (Recommended) - The current collection matches the small data size and avoids premature indexing.
B. Optimize lookup now - Choose this if repeated keyed access is already a measured bottleneck.
C. Preserve ordering semantics - Choose this if stable display order is the real owner of the choice.

Free response: add a different reason if none of these fit.
```

Avoid open-ended essay prompts unless the user explicitly wants a written rationale. The default is recommended choices plus a free-response escape hatch.

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
4. If any rationale is `thin`, either revise the choice, gather evidence, or ask the user one interactive gate.
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
