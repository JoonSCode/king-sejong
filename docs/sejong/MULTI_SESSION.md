# King Sejong Multisession Contract

**Status:** Draft

## Purpose

King Sejong separates three kinds of state so concurrent Codex conversations do
not inherit one another's work:

1. A durable Context is the run-scoped workflow record.
2. A Codex Session Binding identifies the one foreground Context, or an explicit
   unbound tombstone, for one host `session_id`.
3. A Repo Index lists known Contexts for discovery and explicit resume. It never
   selects a Context for a hook.

One repository may have many Contexts and many sessions at once. A session has
at most one foreground Context.

## Runtime Layout

All runtime state remains external under
`${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`:

```text
runs/<repo-id>/<run-id>/king-sejong-context.json
state/session-bindings/<sha256(namespace NUL session-id)>.json
state/session-bindings/history/<binding-id>/*.json
state/repo-index/<repo-identity-hash>.json
state/active-context.json                         # legacy record only
state/legacy-active-context-migration.json        # migration receipt
```

Run artifacts are durable. Session bindings and repo indexes are runtime state
that can be reconstructed from durable artifacts and explicit user choices.
Migration and installation must not delete existing runs.

User-scope runtime authority is also generation-bound. During install,
one stable installer lock owns publication and a frozen source snapshot fixes
the generation bytes. `state/install-transaction.json` remains `in_progress`
while non-canonical content is copied and verified; the canonical hook is
excluded from bulk copy and published atomically only afterward. The complete
marker is the authority commit and includes the epoch and digest. Hooks do not
inject from an incomplete or digest-drifted generation. Installation recovery
and rollback therefore use the current or a previously verified
epoch-2-compatible installer; the supported path rejects a lower authority
epoch before its first live mutation, while a pre-epoch-2 raw installer is
unsupported because it cannot honor this guard.

## Session Binding Authority

Implicit hooks require a non-empty hook payload `session_id`. They resolve only
the binding file whose full SHA-256 name is derived from the host namespace and
that exact session id. The record's internal namespace, session id, binding id,
required fields, timestamps, state, Context ref, and Context id must match.
Missing or unbound sessions stay quiet. Malformed, unknown, mismatched, or
temporarily lock-contended bindings fail closed and never trigger a repository
scan or legacy-pointer fallback. Binding creation and resolution also revalidate
the referenced durable Context field types and shape; a malformed active Context
cannot inject or be resumed into another session.

`turn_id` is an opaque observation id. It is recorded for diagnostics and must
not be lexically or numerically ordered.

Bindings use two counters:

- `binding_epoch` changes only when explicit start, resume, switch, unbind, or
  close changes the target or binding state.
- `revision` changes for every atomic binding mutation, including hook
  observations.

Explicit resume, switch, unbind, and close accept an expected revision and
reject stale writers. Unbind writes a tombstone instead of deleting the file,
so an older writer cannot resurrect a previous epoch. Hook resolution and its
observation update occur under the same per-session lock. A stale observation
whose expected Context id or epoch no longer matches is rejected.

The atomic binding file replacement is the switch commit point. Pause history
and Repo Index updates happen after that commit and are reconstructable; they do
not override the binding if their secondary write fails. Such post-commit
failures are reported as warnings while the bind, switch, unbind, or Context
mutation remains successful and authoritative.

## Durable Context

The durable Context remains under the run directory and carries its own
`context_revision`. Mutations use an independent run-context lock and expected
revision check. The expected revision is mandatory for every create or mutation;
`active_context_id`, `repo_id`, and `run_id` are immutable once the path exists.
Legacy materialization uses this same stable sidecar lock and revision-zero
create boundary, so it cannot replace a Context created concurrently. Binding
compare-and-swap does not protect Context contents.

`context_status` is one of `active`, `paused`, `completed`, or `closed`.
Automatic injection is allowed only for `active`. Closing a Context records its
terminal state and writes an unbound session tombstone; it does not delete the
run artifact.

The historical Context `session_id` field remains provenance and schema
compatibility data. It is not hook-selection authority.

## Exact Repository Identity

Each Context records `repo_identities`, not a broad containment root. A Git
identity is the SHA-256 identity of the repository common Git directory, so Git
worktrees for the same repository match while a nested or sibling Git repository
does not. Non-Git work uses an exact resolved path identity.

Multi-repository work is represented by an explicit list, created with repeated
`--additional-repo-root` arguments. A parent directory does not authorize every
repository beneath it. A bound Context used from a non-matching repository is
not injected.

## Explicit Operations

`sejong_context.py start` creates the durable Context and binds the supplied
session. `resume` explicitly binds or switches a session to an active Context.
`unbind` writes a tombstone. `close` requires the exact session id and expected
binding revision, writes the tombstone as the authority commit, then marks the
Context closed. `update`, `doctor`, and `repair` require either an explicit Context path
or session id; they never infer authority from the legacy pointer.

Forks, side conversations, and new sessions do not inherit a binding. A caller
must explicitly resume or implement a separately approved inherit operation.
Repo Index lookup is suitable for listing candidates for that explicit choice,
not for automatic continuation.

## Legacy Migration

`state/active-context.json` is non-authoritative. `migrate-legacy` preserves its
exact bytes, copies a missing durable run Context when its metadata is usable,
updates the reconstructable Repo Index, and writes a receipt containing the
legacy SHA-256 and `automatic_injection_authority=false`. It creates no session
binding. A malformed legacy file is still preserved and hashed. Unsafe
`repo_id` or `run_id` path components are ignored rather than used as filesystem
destinations, and malformed authority-bearing metadata is not materialized as
derived Context or Repo Index state. The resolved destination must remain under
the configured `runs/` root, and an existing destination is reused only when its
Context, repository, and run identities match the legacy metadata. Both a new
legacy copy and an existing destination must pass the durable Context runtime
contract before either is indexed. Repo Index update failure is recorded as
`repo_index_updated=false` and cannot prevent the migration receipt because the
index is reconstructable and non-authoritative. Likewise, an unavailable runs
destination records `context_materialized=false` while preserving the legacy
bytes and receipt.

The durable materialized copy is a new Context object, not a byte-for-byte
alias of the legacy pointer: its first locked commit adds
`context_revision=1` and a commit timestamp. The original legacy bytes and their
SHA-256 remain unchanged in place.

Explicit `--context` or `SEJONG_ACTIVE_CONTEXT` remains a manual compatibility
path. Missing explicit paths fail closed. This explicit path does not authorize
repo-latest fallback.

## Atomicity and Locks

Session binding, Repo Index, and durable Context mutations use bounded runtime
locks under `state/locks/`. JSON publication uses a unique same-directory
temporary file, file `fsync`, atomic replace, and parent-directory `fsync`.
Lock classes include `session-binding`, `repo-index`, `run-context`,
`artifact-ref`, `team-mailbox`, `team-lease`, `cleanup`, and
`install-maintenance`. `active-pointer` remains only for legacy compatibility.

## Cleanup and Non-Goals

Cleanup may remove only eligible external runtime state and must preserve
durable runs, explicit migration records, promoted artifacts, active or blocked
execution evidence, and dirty worker workspaces. Binding and index reconstruction
must never be implemented by deleting historical run JSON. Destructive cleanup
uses exact active session bindings for run protection, fails closed on malformed
binding state, and neither treats the legacy pointer as foreground authority nor
deletes that preserved legacy record.

This contract does not make hooks a sandbox, add a network coordinator, sync
private Codex state, replace Uigwe or Seungjeongwon authority, or make Repo Index
recency an automatic selection rule.

## Verification Bar

Deterministic tests must cover same-repository two-session isolation, unbound
new sessions, compact resume, explicit switch and handoff, exact nested-repo
isolation, completed and closed Contexts, legacy migration, binding and Context
revision conflicts, tombstone resurrection, and late old-hook observations.
Canonical source, installed source, and actual-shaped `UserPromptSubmit` and
`SessionStart` payloads must be exercised before release.

See [HOOKS.md](HOOKS.md), [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md), and
[CONTINUITY.md](CONTINUITY.md) for lifecycle projection and artifact rules.
