# King Sejong Ambiguity Register

**Status:** Draft

## Purpose

The ambiguity register is King Sejong's external artifact for live clarification.

Use it when a Sejong or Uigwe workflow must show what is still unclear, how clear
the current stage is, what choices the lead agent sees, and what user action is
needed before the workflow may advance.

The schema is [ambiguity-register.schema.json](ambiguity-register.schema.json).
The example is [examples/ambiguity-register.example.json](examples/ambiguity-register.example.json).

## Contract

The register is stored outside the target repository by default under the Sejong
artifact root:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

The active King Sejong context references the register through `artifact_refs`.
The active context does not grow a separate ambiguity state field by default.
Hooks discover readable artifacts whose `format` is
`sejong.ambiguity-register/v0.1-draft`.

## Live Clarification Rule

For live user sessions, Uigwe stage clarification must reach `100%` readiness
before the workflow advances, unless the user explicitly asks to waive the
remaining ambiguity.

If any ambiguity item remains `open`, `pending`, or `answered`, the stage is not
complete. A readiness percentage below `100` is useful progress reporting, not
permission to advance. Each live Uigwe stage stays active until the current
stage reaches `100%` and no question obligation remains, or the user explicitly
asks to skip, waive, or proceed despite the remaining ambiguity.

Use this user-facing shape:

- current stage label, such as `기획 명확화`, `설계 명확화`, or `실행 계약화`
- readiness percentage
- unclear items
- the lead agent's recommended options plus a free-response path
- the next required user action

## Codex Structured Choice UI

When Codex structured choice UI or another host-native structured input surface
is available, Uigwe may present the same open ambiguity through that UI. Put the
recommended option first, include the strongest alternatives that matter, and
keep the user's free-form path available.

The ambiguity register remains the durable source of truth. Codex structured
choice UI is only a presentation adapter, not a separate approval gate, durable
artifact, or reason to advance a stage before the register reaches `100%` or the
user explicitly waives the remaining ambiguity.

`docs/sejong/scripts/live_session_orchestrator.py` can emit the same questions
as both an ambiguity register and `structured_choice_requests` metadata. Use
`--write-register <path>` to persist the register under the Sejong artifact root,
then reference that path from the active context `artifact_refs` so hooks can
enforce it. `structured_choice_requests` entries use the
`codex_structured_choice` adapter name and are presentation hints only.

## Status Semantics

Each ambiguity item has one of these statuses:

- `open`: legacy unresolved state, still blocking advancement
- `pending`: a question has been asked and is waiting for the user's answer
- `answered`: the user has answered, but the lead has not yet accepted the item as resolved or waived
- `resolved`: answered clearly enough to preserve the stage contract
- `waived`: explicitly waived by the user

Open, pending, and answered ambiguities block completion while `blocking=true`.
Waived ambiguities are allowed only when the user explicitly asks to skip,
waive, or proceed despite the ambiguity.
The live clarification exit condition is satisfied only when every blocking question is resolved or when the user explicitly asks to skip, waive, or proceed despite the ambiguity.

## Hook Behavior

When an active context references an ambiguity register:

- `UserPromptSubmit` injects a compact register summary with readiness, open
  ambiguity count, pending question obligation count, and the next required user
  action.
- `PreToolUse` blocks write-like execution while the active Uigwe stage is below
  `100%` readiness or still has unresolved question obligations, except for
  updates to the runtime clarification artifact itself.
- `Stop` blocks completion when any referenced register has open ambiguities or
  pending question obligations.
- `PreCompact` blocks compaction when an ambiguity-register reference is broken.

These hooks preserve the clarification loop. They do not replace Uigwe gates,
Sejong routing, or Seungjeongwon verification.
