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
   - explicit user scope plus a compact execution contract when the task is direct, authorized, and clear
   Reuse current conversation decisions, prior approvals, and applicable rationale refs; do not ask the user to approve them again.
2. When a validated Uigwe bundle or handoff-ready Uigwe state exists, do not replace Seungjeongwon with Sejong direct or ordinary direct edits.
3. Do not reopen planning unless execution discovers a real contradiction.
4. Use native goal backing only when the current host tool conditions are met. Do not infer authorization from tool availability or an ordinary implementation request. If explicit goal creation was not requested, continue the normal execution and verification loop without a native goal.
5. Keep any authorized native goal payload broad: approved objective, completion criteria, verification evidence, blocker policy, and Uigwe re-entry triggers. Use budgets only when explicitly requested. Goal completion and blocked status must meet the current tool contract, including any repeated-blocker threshold; keep the executor todo tree outside the goal.
6. For Uigwe handoff leaves, run todo listup, todo verification, and subtodo decomposition until actionable leaves exist.
7. Complete each actionable leaf only when the Uigwe-defined numeric completion guardrails pass. The default is `0.98` for every leaf guardrail, `0.98` for the leaf aggregate, and `0.98` for the run aggregate; selected leaf coverage and success criteria coverage default to `1.00`.
8. For validation, comparison, review, readiness, or proof goals, choose only the task-specific perspectives that can reveal distinct failures. Split a weak perspective when it leaves a material claim uncovered; do not create roles merely to fill a standard roster.
9. When Codex todo tooling is available, publish actionable leaves as the visible execution board before implementation; append explicit redefinition todos and replacement todos when the execution shape changes instead of silently overwriting the board. When producing machine-readable execution feedback, mirror those visible board changes in `visible_todo_events`.
10. Execute dependency-ready actionable work in the current Codex session when possible.
11. Use parallel workers only when file scopes are independent and verification remains clear. When per-task model assignment is authorized, select a supported model and effort for the task, follow the current host fork/override rules, and record the assignment reason. Do not make every worker use the lead model by habit. `$team` workers require Sejong-owned state, mailbox evidence, and file leases.
12. Preflight worker cleanup before using a host-native backend. Require an exact host identity plus supported release proof; otherwise execute locally or use a Core-owned backend. Register each opened native worker in a resource lease, count terminal-but-unreleased workers as live capacity, and do not fan in or open the next native wave until every lease has a released cleanup receipt. If cleanup fails or cannot be proved, stop spawning, preserve the blocker, and never substitute a process-name or broad child-tree kill.
13. Preserve the approved goal, non-goals, success criteria, must-preserve behavior, and verification bar. Adjust tactics when implementation hypotheses are wrong, but return to Uigwe or human review when those guardrails are unstable.
14. Verify before claiming completion on the surface the user will actually use. Distinguish automated checks, observed user-surface behavior, manual substitution, external publication, and downstream product or business outcomes. Match checks to the changed causal path and broaden them only when a failure, dependency, or material claim requires it.
15. Return execution feedback:
   - completed, blocked, invalidated, or failed scope
   - files changed or artifacts produced
   - native goal id when used; otherwise record the actual reason in existing feedback fields without inventing an enum or claiming that an available tool is missing
   - actionable decomposition evidence
   - verification perspectives and any split, replacement, or rejected perspectives for validation-heavy work
   - paired result comparison when baseline and candidate outputs are judged against the same acceptance criteria
   - visible todo board updates and any redefinition/replacement events
   - `visible_todo_events` when execution feedback is machine-readable
   - attempt ledger summary
   - leaf-level and run-level guardrail scores
   - verification evidence
   - recommended Uigwe re-entry target when needed
   - git evidence when commits are requested or produced

## Boundaries

- Do not invent new scope beyond the approved bundle or explicit user request.
- Do not treat a plan as executed until implementation and verification are done.
- Keep normal execution inside Seungjeongwon.
