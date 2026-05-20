---
name: seungjeongwon
description: Use when a user invokes Seungjeongwon/승정원 or when Sejong needs native execution, verification, execution feedback, commit-ready evidence, or a persistent completion loop for a clear task or validated Uigwe bundle.
---

# Seungjeongwon

`seungjeongwon` is King Sejong's native executor.

Use it to carry an approved scope or validated Uigwe bundle through implementation, verification, evidence capture, and execution feedback.

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
3. Execute dependency-ready work in the current Codex session when possible.
4. Use parallel subagents only when file scopes are independent and verification remains clear.
5. Verify before claiming completion.
6. Return execution feedback:
   - completed, blocked, invalidated, or failed scope
   - files changed or artifacts produced
   - verification evidence
   - recommended Uigwe re-entry target when needed
   - git evidence when commits are requested or produced

## Boundaries

- Do not invent new scope beyond the approved bundle or explicit user request.
- Do not treat a plan as executed until implementation and verification are done.
- Keep normal execution inside Seungjeongwon.
