---
name: seungjeongwon
description: Use when a user invokes Seungjeongwon/승정원 or when Sejong needs native execution, verification, execution feedback, commit-ready evidence, or a persistent completion loop for a clear task or validated Uigwe bundle.
---

# Seungjeongwon

`seungjeongwon` is King Sejong's native executor.

Use it to carry an approved scope or validated Uigwe bundle through actionable todo decomposition, implementation, verification, evidence capture, and execution feedback.

It is included with King Sejong and is the normal execution path.

## Load Order

Read only what is needed:

1. `../../../docs/sejong/SEUNGJEONGWON_EXECUTOR.md`
2. `../../../docs/sejong/CODEX_CONSUMER.md` when executing Uigwe leaves directly
3. `../../../docs/sejong/BUNDLE_VALIDATOR.md` when a bundle path is provided

## Execution Protocol

1. Identify the source of truth:
   - validated Uigwe bundle when present
   - explicit user scope when the task is direct and clear
2. Do not reopen planning unless execution discovers a real contradiction.
3. For a handoff-ready Uigwe bundle whose original request asks for outcome completion, attach execution to a host-native goal when available; the user does not need to type `/goal` separately.
4. Keep native goal payloads broad: approved objective, completion criteria, verification evidence, blocker policy, and Uigwe re-entry triggers. Do not move the executor todo tree into the goal.
5. For Uigwe handoff leaves, run todo listup, todo verification, and subtodo decomposition until actionable leaves exist.
6. For validation, comparison, review, readiness, or proof goals, decompose the verification objective into task-specific perspectives, verify those perspectives are sufficient, split weak perspectives, and then execute the verification.
7. When Codex todo tooling is available, publish actionable leaves as the visible execution board before implementation; append explicit redefinition todos and replacement todos when the execution shape changes instead of silently overwriting the board. When producing machine-readable execution feedback, mirror those visible board changes in `visible_todo_events`.
8. Execute dependency-ready actionable work in the current Codex session when possible.
9. Use parallel workers only when file scopes are independent and verification remains clear. `$team` workers require Sejong-owned state, mailbox evidence, and file leases.
10. Preserve the approved goal, non-goals, success criteria, must-preserve behavior, and verification bar. Adjust tactics when implementation hypotheses are wrong, but return to Uigwe or human review when those guardrails are unstable.
11. Verify before claiming completion.
12. Return execution feedback:
   - completed, blocked, invalidated, or failed scope
   - files changed or artifacts produced
   - native goal id or `native_goal_unavailable` when relevant
   - actionable decomposition evidence
   - verification perspectives and any split, replacement, or rejected perspectives for validation-heavy work
   - paired result comparison when baseline and candidate outputs are judged against the same acceptance criteria
   - visible todo board updates and any redefinition/replacement events
   - `visible_todo_events` when execution feedback is machine-readable
   - attempt ledger summary
   - verification evidence
   - recommended Uigwe re-entry target when needed
   - git evidence when commits are requested or produced

## Boundaries

- Do not invent new scope beyond the approved bundle or explicit user request.
- Do not treat a plan as executed until implementation and verification are done.
- Keep normal execution inside Seungjeongwon.
