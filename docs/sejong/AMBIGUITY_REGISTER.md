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

If any ambiguity item remains `open`, the stage is not complete. A readiness
percentage below `100` is useful progress reporting, not permission to advance.

Use this user-facing shape:

- current stage label, such as `기획 명확화`, `설계 명확화`, or `실행 계약화`
- readiness percentage
- unclear items
- the lead agent's recommended options
- a free-response path
- the next required user action

## Status Semantics

Each ambiguity item has one of these statuses:

- `open`: unresolved and blocking advancement
- `resolved`: answered clearly enough to preserve the stage contract
- `waived`: explicitly waived by the user

Open ambiguities block completion. Waived ambiguities are allowed only when the
user explicitly asks to skip, waive, or proceed despite the ambiguity.

## Hook Behavior

When an active context references an ambiguity register:

- `UserPromptSubmit` injects a compact register summary with readiness, open
  ambiguity count, and the next required user action.
- `Stop` blocks completion when any referenced register has open ambiguities.
- `PreCompact` blocks compaction when an ambiguity-register reference is broken.

These hooks preserve the clarification loop. They do not replace Uigwe gates,
Sejong routing, or Seungjeongwon verification.
