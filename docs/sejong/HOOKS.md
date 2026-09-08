# King Sejong Hooks

**Status:** Draft

## Purpose

Hooks are King Sejong guardrails for the Codex lifecycle.

They do not replace Codex, permissions, sandboxing, Sejong routing, Uigwe gates, or Seungjeongwon verification. They inject active context, catch supported protected actions, and preserve evidence so the lead Sejong agent can keep the workflow on the intended route.

The reference implementation is:

```bash
python3 docs/sejong/scripts/king_sejong_hooks.py <event-name> --context <context.json>
```

Active context checkpoints can be created, updated, diagnosed, and closed with:

```bash
python3 docs/sejong/scripts/sejong_context.py start --repo-root . --session-id <codex-session-id>
python3 docs/sejong/scripts/sejong_context.py update --session-id <codex-session-id> --append-route seungjeongwon --add-pending-gate verification
python3 docs/sejong/scripts/sejong_context.py doctor --session-id <codex-session-id> --repo-root .
python3 docs/sejong/scripts/sejong_context.py close --session-id <codex-session-id>
```

Hook behavior is scoped by the why-based force levels in
[DISCIPLINE_GATES.md](DISCIPLINE_GATES.md). Hooks may enforce `hard` gates such
as protected self-modification, premature completion, worker authority claims,
open ambiguity, and active Seungjeongwon runs. They may route or add context for
an explicitly recorded Uigwe promotion gate. They should not infer that gate
from research, advice, a future possible plan, or ordinary goal-bearing
execution, and should not turn every advisory practice into a hard block.

The reference tests are:

```bash
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_context.py
python3 docs/sejong/scripts/test_session_binding_context.py
python3 docs/sejong/scripts/test_king_sejong_multisession_e2e.py
SEJONG_HOME="$(mktemp -d)" python3 docs/sejong/scripts/test_king_sejong_e2e.py
```

## Active Context

Hooks consume a King Sejong active context checkpoint. The schema is [king-sejong-context.schema.json](king-sejong-context.schema.json), and the example is [examples/king-sejong-context.example.json](examples/king-sejong-context.example.json).

The checkpoint is external runtime state by default. It should be stored under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/<repo-id>/<timestamp>-<run-id>/
```

Required state includes:

- `active_context_id`
- `route_id`
- `current_surface`
- `route_sequence`
- `required_route_sequence`
- `pending_gates`
- `protected_paths`
- `allowed_direct_change_types`
- `evidence_refs`
- `artifact_refs`
- `team_run_refs`
- `subagent_refs`
- `exit_conditions`

Optional current-run HUD metadata includes:

- `objective_id`
- `objective_refs`

Use these fields for product wedges, cross-repo objectives, migration notes, or
design artifacts that should remain visible across follow-up prompts,
compaction, and repository/worktree changes. They do not replace Uigwe packets
or Seungjeongwon run artifacts.

Active context includes `uigwe_promotion_required` only when the user explicitly
requests Uigwe or joint intent/design discovery, or when authorized execution
has a material unresolved planning boundary. The gate remains pending across
unrelated current-surface and route-history updates. Context update clears it
only when the current required Uigwe entry is explicitly recorded with
`--current-surface uigwe`, `--append-route uigwe`, or a
`--set-route-sequence` whose final item is `uigwe`, or when the user explicitly
changes the requested scope. Earlier Uigwe route history, including membership
elsewhere in a newly set sequence, does not satisfy the boundary. Research,
review, comparison, recommendation, and proposal-only work do not create this
gate merely because the result might inform later work.

A goal-bearing context defaults to required route `seungjeongwon` and
`seungjeongwon_receipt_required`. It does not imply Uigwe. When both a real Uigwe
boundary and execution apply, adding required route `uigwe` to a settled
required sequence containing `seungjeongwon` inserts Uigwe immediately before
Seungjeongwon while preserving the order of other required guards. Hooks enforce
the pending gate itself rather than treating old route history as satisfaction
or inventing a gate.
Record that boundary with `start --required-route uigwe` or
`update --add-required-route uigwe`. The context helper adds
`uigwe_promotion_required` until one of the explicit current-entry updates above
records the required entry and context update clears the gate. An
explicit `--clear-pending-gate uigwe_promotion_required` before entry also
removes the unresolved Uigwe required route while preserving any independent
Seungjeongwon receipt obligation.

When `artifact_refs` includes a readable artifact whose `format` is
`sejong.ambiguity-register/v0.1-draft`, hooks treat it as the active ambiguity
register. Blocking `open`, `pending`, and `answered` items are live question
obligations until resolved or explicitly waived. See
[AMBIGUITY_REGISTER.md](AMBIGUITY_REGISTER.md).

When `artifact_refs` includes a readable artifact whose `format` is
`sejong.seungjeongwon-run/v0.1-draft`, hooks treat it as an active
Seungjeongwon execution run. See [seungjeongwon-run.schema.json](seungjeongwon-run.schema.json).

## Event Responsibilities

`SessionStart`

- Load only the active Context bound to the exact payload `session_id`.
- Stay quiet for a new, forked, side, unbound, completed, or closed session;
  never select the newest repository Context.
- Inject a compact King Sejong continuation summary.
- Treat `source=compact` as the supported post-compaction reinjection path.
  Include active Seungjeongwon run summaries and continuity capsule projections
  through `hookSpecificOutput.additionalContext` on this event.

`UserPromptSubmit`

- Keep follow-up turns inside the active King Sejong workflow unless the user explicitly exits.
- Add model-visible context with the active context id, route id, repo root,
  objective id, task class, projection profile, current surface, route sequence,
  pending gates, objective refs, and last user intent.
- Inject a compact ambiguity register summary when a referenced register exists, including readiness, blocking open ambiguity count, pending question obligation count, and next required user action. Optional preferences do not block completion; required-stage readiness excludes optional preferences.
- Inject a compact continuity capsule projection when a referenced capsule
  exists. The projection is model-visible working-set context, not the full
  capsule and not a gate approval.

`sejong_context.py` stores the durable checkpoint in its run directory and
publishes a separate binding for the exact hook payload `session_id`. Hooks read
only that session binding for implicit continuation. Repo Index and the legacy
`state/active-context.json` file have no automatic injection authority.

`PreToolUse`

- Inspect supported tool calls for protected King Sejong paths.
- Allow read-only protected-path inspection; protected reads are evidence
  gathering, not self-modification.
- Deny write-like material self-modification when the required route sequence is
  missing.
- Treat common interpreter write snippets as write-like when they target a
  protected path, including Python `open(..., "w")` or `Path.write_text`, Node
  filesystem writes, Ruby `File.write`, and Perl open/sysopen write modes.
- Deny write-like or execution-completion tool calls while an explicitly recorded `uigwe_promotion_required` is pending. The pending gate itself is unresolved authority even if route history contains an earlier Uigwe entry. Do not synthesize this gate from goal-bearing state, research, advice, or route history alone.
- Deny write-like execution while `seungjeongwon_receipt_required` is pending
  until the route has entered Seungjeongwon and the active context references a
  valid `sejong.seungjeongwon-run/v0.1-draft` artifact or an explicit
  `sejong.seungjeongwon-receipt/v0.1-draft` artifact whose
  `receipt_type` is `native_goal_unavailable`.
- Deny write-like execution while the current Uigwe live stage has a referenced
  ambiguity register below `100%` readiness or with blocking `open`, `pending`,
  or `answered` question obligations. Runtime clarification artifact updates
  remain allowed so Uigwe can record the user's answer or waiver.
- Do not infer a receipt gate from `required_route_sequence` alone. Route
  history records the intended path; `seungjeongwon_receipt_required` records an
  explicit unfinished execution obligation.
- Add context instead of denying when write-like protected paths are touched
  after route evidence exists.

`PermissionRequest`

- Deny escalated protected edits when route evidence is missing.
- Deny escalated write-like or execution-completion requests while an explicitly recorded `uigwe_promotion_required` is pending; unrelated current-surface or route-history updates do not clear it.
- Deny escalated write-like or execution-completion requests while
  `seungjeongwon_receipt_required` is pending before a valid Seungjeongwon
  receipt exists.
- Leave normal approval flow alone when no protected route is involved.

`PostToolUse`

- Record or surface verification obligations after write-like protected paths
  are touched.
- This hook cannot undo side effects; it only guards the next model step.

`SubagentStart`

- Inject the active context summary plus a bounded worker contract with worker
  role, worker scope, source-of-truth refs, allowed outputs, forbidden authority
  claims, return format, and stop condition.

`TaskCreated`, `TaskCompleted`, `TeammateIdle` when the host runtime supports team or teammate hooks

- Keep official team-task and teammate events inside the same Sejong authority model.
- Reject teammate output or task completion that claims Uigwe gate approval, final synthesis, final verification, consensus approval, or majority-vote authority.
- Add active context for bounded peer messages, shared task state, and
  lead-owned synthesis. `TaskCreated` should inject the same bounded worker
  contract shape used by `SubagentStart` when role and scope metadata are
  available.

`SubagentStop`

- Require a parseable JSON `sejong.bounded-worker-brief/v0.2-draft` final
  response and validate objective, role, source-of-truth refs, allowed outputs,
  forbidden claims, write scope, stop condition, and evidence refs before the
  worker output can be treated as evidence.
- Reject worker outputs that claim Uigwe gate approval, final synthesis, final
  verification, or majority-vote authority.
- Treat the bounded brief as terminal output evidence, not cleanup evidence.
  Host-native runtime teardown happens after the worker stops and must be
  projected through a worker resource lease plus cleanup receipt. Do not kill
  MCP or tool-server processes from this pre-teardown hook.

`Stop`

- Continue the turn when pending gates or missing verification would make completion premature.
- Continue the turn when an explicitly recorded `uigwe_promotion_required` remains pending, so a real unresolved or requested Uigwe boundary cannot be bypassed. Research or advice without that gate may end at its requested terminal deliverable.
- Continue the turn when `seungjeongwon_receipt_required` remains pending, so
  goal-bearing implementation cannot end before a Seungjeongwon execution
  receipt exists.
- Continue the turn when any referenced ambiguity register still has `open`
  ambiguity items or pending question obligations.
- Continue the turn when any referenced Seungjeongwon run is active, broken, or invalid.
- A referenced Seungjeongwon run backed by native delegation remains active
  until every `codex-thread://` worker has a released cleanup receipt and fan-in
  passes; terminal worker output alone cannot satisfy `Stop`.
- Continue the turn when any referenced continuity capsule is broken or invalid.

`PreCompact`

- Do nothing when the exact session has no bound active Context. Do not scan the
  repository, Repo Index, or legacy pointer.
- Fail closed when the exact session binding is malformed, schema-incomplete,
  mismatched, lock-contended, or points to an unreadable or invalid Context.
- Fail closed when an explicit `--context` path or `SEJONG_ACTIVE_CONTEXT`
  path is missing.
- Check that the active context checkpoint has the required fields before
  compaction.
- Block compaction when a referenced ambiguity register or continuity capsule
  is broken or invalid. Block unreadable Seungjeongwon run refs and invalid
  active Seungjeongwon runs.
- For each valid referenced active `sejong.seungjeongwon-run/v0.1-draft` artifact,
  write a derived `sejong.seungjeongwon-checkpoint/v0.1-draft` artifact under
  `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`.
- Emit no success payload. Codex compact hook outputs do not accept
  `hookSpecificOutput`; post-compaction context is injected by
  `SessionStart(source=compact)` instead.

## Config

User-scope King Sejong install enables hooks through the local
`king-sejong-local` Codex plugin by default. The plugin hook is a thin adapter
that delegates to the canonical user-scope script under
`${CODEX_HOME:-~/.codex}/skills/sejong/docs/scripts/king_sejong_hooks.py`.
If Codex launches the adapter with Python older than 3.11, the adapter uses
`uv` to run that canonical script with Python 3.11. Legacy-direct installation
also registers the adapter so both modes follow the same runtime selection path.
The adapter disables Python bytecode writes so hook execution does not leave
cache directories inside installer-managed paths. A forced reinstall removes
stale bytecode caches left by older adapters.
If that canonical script is missing, the adapter stays quiet for non-protected
events but returns a non-zero error for protected lifecycle events such as
`PreToolUse`, `PermissionRequest`, `Stop`, and `PreCompact`.
The installer owns a marked King Sejong plugin block and sets
`[features].hooks = true`. Exact repository identities resolve symlink aliases
and Git common directories before hashing canonical filesystem bytes; they do
not unconditionally case-fold distinct paths on case-sensitive macOS volumes.

User-scope installation publishes a fail-closed maintenance generation before
copying any authority-bearing runtime file. A stable per-`CODEX_HOME` installer
lock serializes concurrent publishers. After read-only downgrade preflight, the
installer captures a frozen managed-source snapshot, atomically publishes the
maintenance hook, and records `state/install-transaction.json` as
`in_progress`. Bulk docs copy excludes the canonical hook in both the rsync and
fallback paths. All other managed content and configuration are verified from
the snapshot before the staged canonical hook is atomically published. A final
read-only verification precedes the atomic `complete` marker with runtime
authority epoch `2` and the combined installed digest. The adapter permits
automatic injection only when that marker is complete and the installed digest
matches. An interrupted, missing, or drifted generation stays quiet for
non-protected events and rejects protected lifecycle events. Rerunning the same
installer is the recovery path.

The process-crash guarantee begins at the atomic maintenance-hook commit. Hook
processes that started before that commit cannot be retroactively stopped by a
file replacement. From that commit until the final complete marker, a hook sees
only maintenance or missing canonical authority, or a staged epoch-2 canonical
whose adapter still rejects the `in_progress` generation.

A supported rollback is a forced reinstall from a previously captured,
verified epoch-2-compatible King Sejong source followed by `--verify`. A raw
downgrade to a source predating the install-transaction adapter is not a safe
rollback: that older code cannot validate the maintenance marker and may
restore legacy active-pointer authority. Preserve such historical sources for
forensics only; do not execute their user-scope installer over an epoch-2
installation.

Older installs may still have a marked direct hook block in
`${CODEX_HOME:-~/.codex}/config.toml`. A normal user-scope reinstall removes
that direct block so plugin hooks are the single canonical hook source. The
explicit `--legacy-direct-hooks` installer option keeps direct hooks as a
fallback mode, but verification fails when direct hooks and plugin hooks are
enabled together.

Hooks are scoped by the payload `session_id`, with `turn_id` recorded as an
opaque observation id. The reference hook hashes the host namespace and exact
session id, validates the internal binding identity, and loads only its bound
durable Context. New sessions, forks, and side conversations remain unbound
until explicit resume or inherit. Missing bindings stay quiet. Unknown,
malformed, mismatched, completed, and closed state fails closed without a
repository-latest fallback.

Repository fit uses exact identities. Git worktrees share the common Git
directory identity, while nested and sibling Git repositories do not. Multiple
repositories require an explicit Context identity list; a broad parent
`repo_root` is not containment authority.

An explicit `--context` path or `SEJONG_ACTIVE_CONTEXT` path is not a hint; if
it is missing, hooks surface `missing_explicit_active_context=true` instead of
falling back to another repo-scoped context. An implicitly bound Context used
from a different exact repository stays quiet and exposes none of that Context.
An explicit manual Context may surface a `repo_mismatch=true` diagnostic.
Broken artifact refs inside the selected Context remain explicit obligations
and fail closed for compaction and completion gates.

A target repo or user profile can also wire the reference scripts manually:

```toml
[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "python3 /path/to/docs/sejong/scripts/king_sejong_hooks.py UserPromptSubmit --context /path/to/context.json"
timeout = 30

[[hooks.PreToolUse]]
matcher = "Bash|apply_patch|Edit|Write"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "python3 /path/to/docs/sejong/scripts/king_sejong_hooks.py PreToolUse --context /path/to/context.json"
timeout = 30

[[hooks.SubagentStop]]
matcher = ".*"

[[hooks.SubagentStop.hooks]]
type = "command"
command = "python3 /path/to/docs/sejong/scripts/king_sejong_hooks.py SubagentStop --context /path/to/context.json"
timeout = 30

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = "python3 /path/to/docs/sejong/scripts/king_sejong_hooks.py Stop --context /path/to/context.json"
timeout = 30
```

Manual direct hooks are legacy fallback wiring. The installer keeps normal
plugin-based installs idempotent by replacing only the managed King Sejong
plugin block and removing the old managed direct hook block.

## Limits

Hooks are deterministic guardrails, not a complete enforcement boundary.

`PreToolUse` and `PostToolUse` are especially useful, but Codex does not guarantee interception of every possible equivalent tool path. King Sejong still requires source review, schema validation, TeamExecutor checks, instruction-surface benchmarks, installer verification, and Seungjeongwon final verification before claiming completion.
