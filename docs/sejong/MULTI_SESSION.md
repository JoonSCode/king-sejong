# King Sejong Multisession Contract

**Status:** Draft

## Purpose

King Sejong can be used from multiple Codex sessions, repositories, devices, and
worker backends at the same time. This contract defines the generic public core
rules for identifying sessions and runs, selecting active context safely, locking
shared runtime state, handling stale pointers, and cleaning up runtime artifacts.

The guiding rule is simple: the active pointer is a hint, and the run-scoped
context is the source of truth for a King Sejong workflow.

## Identity Fields

Use distinct ids for distinct ownership boundaries:

- `session_id`: one host conversation or Codex process lifecycle. It changes
  when the user starts a separate session, even if the objective and repository
  are the same.
- `run_id`: one King Sejong workflow run under the Sejong artifact root. It
  groups active context, route decisions, evidence refs, continuity capsules,
  Seungjeongwon runs, Sillok traces, and related runtime artifacts.
- `repo_id`: a stable repository namespace used under the Sejong artifact root.
  It should separate repositories without leaking unnecessary host detail. A
  readable slug plus a short hash of the repository root is sufficient.
- `device_id`: a stable local device namespace for diagnostics and lock owner
  metadata. It should distinguish machines without becoming an account,
  credential, or cross-device sync mechanism.

`active_context_id`, `route_id`, objective ids, worker ids, message ids, and
lease ids remain scoped to their existing contracts. They do not replace
`session_id`, `run_id`, `repo_id`, or `device_id`.

## Runtime Layout

Runtime state belongs under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

Repository-scoped runs live under:

```text
runs/<repo-id>/<timestamp>-<run-id>/
```

The run directory owns the authoritative workflow files for that run, such as
`king-sejong-context.json`, `continuity-capsule.json`, `seungjeongwon-run.json`,
route logs, execution evidence, and Sillok traces.

TeamExecutor coordination state remains under:

```text
state/team/<run-id>/
```

Team state is runtime evidence and coordination state. It is not the active
context source of truth unless a run context explicitly references it.

## Active Pointer Semantics

The active pointer is the convenience file at:

```text
state/active-context.json
```

It is a fast lookup hint for hook and session-start behavior. It is not an
authority layer and is not proof that the pointed run is current.

Every consumer must treat the run-scoped context as authoritative:

1. Read the active pointer when it exists.
2. Verify that the pointed context is readable and valid.
3. Verify that the context matches the current repository, objective when known,
   and expected workflow evidence.
4. If the pointer is missing or stale, search repository-scoped run contexts for
   the newest valid matching context.
5. If a matching run context exists, use that run-scoped context and surface that
   pointer fallback happened.
6. If the active pointer points at a sibling repository or unrelated objective,
   surface `repo_mismatch` or an equivalent warning and do not apply that
   context as authority.

An explicit context path is different from the active pointer. When a user or
hook invocation supplies an explicit `--context` path or `SEJONG_ACTIVE_CONTEXT`,
that path is the requested source. If it is missing or unreadable, report the
explicit-context failure instead of falling back silently.

## Stale Pointer Behavior

A pointer is stale when any of these are true:

- the pointed file is missing, unreadable, malformed, or schema-invalid
- `repo_root` does not cover the current workspace
- the objective, task class, route, or evidence basis no longer matches the
  current work
- referenced ambiguity registers, continuity capsules, Seungjeongwon run
  artifacts, Sillok traces, or evidence manifests are broken
- the pointer is older than a newer valid matching run context for the same
  repository and active workflow class

Stale pointers are not fatal by themselves. Continuation events should prefer a
newest valid matching run context when one exists. Completion, compaction,
protected writes, and explicit context usage must fail closed when required
referenced artifacts are broken or the explicit context cannot be trusted.

## Lock Classes

Shared runtime mutations must use file locks under:

```text
state/locks/
```

The lock record should include lock name, lock class, owner `session_id`,
`run_id` when applicable, `repo_id` when applicable, `device_id`, process id
when available, creation time, heartbeat or update time when supported, and a
human-readable operation summary.

Use these lock classes:

- `active-pointer`: guards writes to `state/active-context.json` and prevents
  two sessions from racing to publish different active hints.
- `run-context`: guards writes to a run's `king-sejong-context.json` and closely
  related route or artifact refs.
- `artifact-ref`: guards append or rewrite operations that update shared
  evidence manifests, Sillok traces, continuity capsules, or execution feedback
  refs for one run.
- `team-mailbox`: guards TeamExecutor mailbox and round mutations. This aligns
  with the existing per-run TeamExecutor mailbox lock.
- `team-lease`: guards TeamExecutor lease acquisition and release when the lease
  operation is not already covered by the mailbox critical section.
- `cleanup`: guards destructive runtime cleanup and pruning so active runs,
  dirty worker workspaces, and promoted artifacts cannot be deleted while
  another session is still evaluating them.
- `install-maintenance`: guards user-scope install, update, and verification
  maintenance that mutates managed King Sejong install surfaces.

Lock acquisition should be bounded. A session that cannot acquire a required
lock must report the owner metadata, lock class, waited duration, and next safe
action. It must not pretend the mutation succeeded.

Stale locks require conservative handling. A lock can be considered stale only
when the owner process is gone or the lock age exceeds the documented stale
threshold for that lock class. Breaking a stale lock should record the previous
metadata and the reason. Cleanup must never break a lock for an active run only
because it is inconvenient.

## Cleanup Safety

Cleanup is allowed only for external runtime artifacts under the Sejong artifact
root. It must not delete repository-tracked files, managed install files, user
configuration outside the managed King Sejong blocks, or promoted artifacts.

Cleanup must preserve:

- the active run referenced by a valid active pointer or matching run context
- any run with active, invalid, or unresolved Seungjeongwon execution state
- any run with open ambiguity, broken evidence refs, or blocked continuation
- runs with promotion markers such as `promoted-artifacts.json` or
  `.sejong-promoted`
- dirty TeamExecutor worker workspaces until the lead inspects them
- compact evidence needed for later review, such as Sillok records, evidence
  manifests, continuity capsules, run summaries, and execution feedback

Destructive cleanup should default to dry-run reporting. Execution requires an
explicit cleanup action, a cleanup lock, and a report of deleted and retained
paths with reasons.

## Concurrent Session Rules

Multiple sessions may work in the same repository when their run contexts,
objective ids, and write scopes are distinct. They must not share mutable
workflow state through the active pointer.

For same-repository concurrent work:

- every session must have its own `session_id`
- every workflow run must have its own `run_id`
- the active pointer may point at only one recent context and remains a hint
- hooks must verify repo and objective fit before injecting context
- protected writes must use route evidence and current verification evidence
- worker mailbox output is evidence for the lead, not gate authority

For cross-repository concurrent work:

- repository-scoped run directories are separated by `repo_id`
- a stale active pointer from a sibling repository must produce `repo_mismatch`
  or equivalent context, not silent adoption
- fallback selection must prefer newest valid contexts whose `repo_root`
  contains the current workspace

For cross-device work:

- `device_id` appears in diagnostics, lock owner metadata, and reports
- King Sejong core does not sync raw Codex state, credentials, sqlite stores,
  caches, or unbounded session logs
- a run remains authoritative because of its run-scoped context and evidence
  refs, not because another device copied an active pointer

## Non-Goals

- This does not make the active pointer authoritative.
- This does not introduce repo-local or tool-specific orchestration state as a
  King Sejong dependency.
- This does not replace Uigwe planning gates, Sejong lead synthesis, or
  Seungjeongwon final verification.
- This does not turn TeamExecutor workers, native subagents, or teammate
  messages into gate approvers.
- This does not add private profiles, personal workflows, app-specific policies,
  credentials, or raw `~/.codex` sync to the public core install surface.
- This does not require network coordination services for local multisession
  safety.
- This does not make cleanup a repair mechanism for broken runs. Broken refs
  should be reported, blocked, or repaired explicitly before deletion.

## Related Contracts

- [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md) defines the external artifact root,
  run directories, retention, and promotion rules.
- [HOOKS.md](HOOKS.md) defines active context injection, stale pointer fallback,
  explicit context behavior, repo mismatch warnings, and lifecycle gates.
- [CONTINUITY.md](CONTINUITY.md) defines compact continuation state and
  stale-state triggers.
- [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) defines worker mailbox and lease state,
  per-run locking, bounded worker authority, and cleanup of worker workspaces.
- [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md) defines execution run
  artifacts, checkpoint behavior, and final verification ownership.
