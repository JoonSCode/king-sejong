# Optional Adapters

**Status:** Conservative adapter plan

## Purpose

King Sejong stays Codex-native by default. Optional adapters can improve
discoverability, code intelligence, specialist review, and handoff ergonomics,
but they must not become hidden runtime dependencies or alternate authorities.

Use this document when adding LazyCodex-style product surfaces without copying
LazyCodex's state model or permission model.

For user-facing default/detail/specialist behavior, use the UX profile contract
in [UX_PROFILES.md](UX_PROFILES.md). Profiles are presentation and helper
selection overlays, not court modes.

## Adapter Rules

All optional adapters must follow these rules:

- default install remains the current skill and docs surface
- no silent model, provider, sandbox, approval, or config mutation
- no telemetry or background auto-update
- no repo-local runtime state dependency
- worker, specialist, or tool output remains evidence
- Sejong lead owns synthesis and final routing
- Uigwe owns planning approval
- Seungjeongwon owns execution completion and verification evidence
- uninstall, repair, and update actions require explicit user intent

Every adapter output that claims a UX profile must include `owner_surface`,
`next_surface`, `claim_type`, `known`, `inferred`, `unknown`, and
`forbidden_claims`. Required forbidden claims are `no_gate_approval`,
`no_execution_approval`, and `no_completion_claim`. Validate profile-like output
with:

```bash
python3 docs/sejong/scripts/ux_profile_contract.py <profile-output.json>
```

## Codex Agent Roles

The examples in `docs/sejong/examples/codex-agents/` define narrow Codex custom
agent roles for bounded research, criticism, and verification.

They are examples, not required install surfaces. A repo or user-scope adapter
may copy them only as optional role templates and must preserve the rule that
custom agents cannot approve gates, claim consensus, or complete final
verification unless the Sejong lead requested only a bounded note.

## Code Intelligence

Optional code-intelligence integrations may use LSP, AST search, code graph, or
context-provider tools to gather evidence faster.

Allowed use:

- symbol discovery
- call graph or reference search
- structured AST matching
- local source summaries
- read-only impact analysis

Disallowed use:

- replacing source inspection with unsourced claims
- treating tool output as final authority
- adding mandatory MCP servers to core install
- mutating editor, model, or approval configuration

## Specialist Packs

Specialist skills such as frontend QA, security review, release readiness,
schema review, or git hygiene can be useful as bounded lenses.

Add them as optional routing aids, not broad global triggers. Each specialist
must declare:

- input scope
- files or surfaces it may inspect
- allowed output
- verification expectation
- stop condition
- forbidden claims
- owner surface and next surface

## Marketplace And Remote Install

A future npm or marketplace wrapper may delegate to `scripts/install-sejong.sh`.
That wrapper should be a transport convenience only.

It must not:

- become the source of truth for behavior
- bypass `scripts/install-sejong.sh --verify`
- silently self-update hooks
- mutate non-Sejong config blocks
- copy source-only `AGENTS.md` into target repositories

The first productization target is a read-only doctor and clear public docs.
Remote packaging comes after those checks are stable.
