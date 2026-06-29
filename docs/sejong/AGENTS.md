# King Sejong Protocol Docs

## Overview

This directory is the durable contract surface for Sejong routing, Uigwe planning, Seungjeongwon execution, TeamExecutor coordination, hooks, schemas, and validation.

## Where To Look

| Task | Location | Notes |
| --- | --- | --- |
| Runtime contract | `RUNTIME_CONTRACT.md`, `ROLE_SEPARATION.md` | Codex-native boundaries and court-mode authority. |
| Routing | `ROUTER.md`, `SEJONG.md` | User-facing workflow selection and follow-up behavior. |
| Research/adapters | `DEEP_RESEARCH.md`, `OPTIONAL_ADAPTERS.md`, `DOCTOR.md` | Deep research protocol, optional integrations, install health checks. |
| Formal planning | `PROTOCOL.md`, `WRAPPER.md`, `SCORING_AND_GATES.md` | Uigwe packets, gates, scoring, handoff shape. |
| Execution | `SEUNGJEONGWON_EXECUTOR.md`, `EXECUTOR.md` | Todo decomposition, verification, retry, evidence. |
| UX profiles | `UX_PROFILES.md`, `scripts/ux_profile_contract.py` | UX profile contract and validation surface. |
| Team coordination | `TEAM_EXECUTOR.md`, `team-executor.schema.json` | Mailbox/state/lease contracts for `$team`. |
| Artifact storage | `ARTIFACT_STORAGE.md`, `CONTINUITY.md`, `AMBIGUITY_REGISTER.md` | Runtime state roots, capsules, registers. |
| Hooks | `HOOKS.md`, `REPO_CONTEXT.md`, `scripts/king_sejong_hooks.py` | Lifecycle guardrails and active repo context. |
| Evidence/security | `SILLOK_TRACE.md`, `SECURITY.md`, `DISCIPLINE_GATES.md` | Trace, risk, rationale, and approval boundaries. |
| Validation | `VALIDATION.md`, `EVALS.md`, `scripts/benchmark_instruction_surface.py` | Behavior benchmarks and instruction-surface gates. |
| Schemas | `*.schema.json`, `policy.defaults.json` | Keep docs, examples, scripts, and tests aligned. |

## Conventions

- Durable behavior belongs here before it is reflected in thin skill front doors.
- Schema, examples, scripts, tests, and docs move together for behavior changes.
- Runtime artifacts stay under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless explicitly promoted.
- Lead Sejong synthesis owns gates and final decisions; worker or mailbox output is evidence, not approval.
- Keep repo-local prompt overlays optional.
- Run local validation scripts when changing protocol behavior, hook behavior, doctor checks, or UX profile contracts.

## Anti-Patterns

- Do not add repo-local or tool-specific orchestration state as a Sejong dependency.
- Do not treat hooks as a complete sandbox.
- Do not let TeamExecutor consensus, worker silence, or mailbox state replace outcome verification.
- Do not expose duplicate plugin-scoped skills when installer-owned user-scope skills are canonical.
