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
python3 docs/sejong/scripts/sejong_context.py start --repo-root .
python3 docs/sejong/scripts/sejong_context.py update --append-route seungjeongwon --add-pending-gate verification
python3 docs/sejong/scripts/sejong_context.py doctor --repo-root .
python3 docs/sejong/scripts/sejong_context.py close
```

Hook behavior is scoped by the why-based force levels in
[DISCIPLINE_GATES.md](DISCIPLINE_GATES.md). Hooks may enforce `hard` gates such
as protected self-modification, premature completion, worker authority claims,
open ambiguity, and active Seungjeongwon runs. They may route or add context for
`route` gates such as research-to-Uigwe promotion. They should not turn every
advisory practice into a hard block.

The reference tests are:

```bash
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_context.py
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

For research that is explicitly meant to feed a decision or later Uigwe plan,
active context should include `uigwe_promotion_required` in `pending_gates`
until Uigwe starts or the user explicitly converts the request to research-only.
This prevents a research or council note from being treated as the final
workflow conclusion.

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

- Load recent active context for the repository when available.
- If the active pointer is missing or stale, select the newest valid matching
  run context under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs`
  when one exists.
- Inject a compact King Sejong continuation summary.

`UserPromptSubmit`

- Keep follow-up turns inside the active King Sejong workflow unless the user explicitly exits.
- Add model-visible context with the active context id, route id, repo root,
  objective id, task class, projection profile, current surface, route sequence,
  pending gates, objective refs, and last user intent.
- Inject a compact ambiguity register summary when a referenced register exists, including readiness, open ambiguity count, pending question obligation count, and next required user action.
- Inject a compact continuity capsule projection when a referenced capsule
  exists. The projection is model-visible working-set context, not the full
  capsule and not a gate approval.

`sejong_context.py` writes the same checkpoint to both the active pointer under
`${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/active-context.json` and
the repository-scoped run directory. Hooks read the active pointer by default.

`PreToolUse`

- Inspect supported tool calls for protected King Sejong paths.
- Allow read-only protected-path inspection; protected reads are evidence
  gathering, not self-modification.
- Deny write-like material self-modification when the required route sequence is
  missing.
- Deny write-like or execution-completion tool calls while `uigwe_promotion_required` is pending and the route has not entered `uigwe`.
- Deny write-like execution while `seungjeongwon_receipt_required` is pending
  until the route has entered Seungjeongwon and the active context references a
  valid `sejong.seungjeongwon-run/v0.1-draft` artifact or an explicit
  `native_goal_unavailable` execution-feedback ref.
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
- Deny escalated write-like or execution-completion requests while `uigwe_promotion_required` is pending before Uigwe entry.
- Deny escalated write-like or execution-completion requests while
  `seungjeongwon_receipt_required` is pending before a valid Seungjeongwon
  receipt exists.
- Leave normal approval flow alone when no protected route is involved.

`PostToolUse`

- Record or surface verification obligations after write-like protected paths
  are touched.
- This hook cannot undo side effects; it only guards the next model step.

`SubagentStart`

- Inject the bounded worker contract, source-of-truth refs, and forbidden authority claims.

`TaskCreated`, `TaskCompleted`, `TeammateIdle` when the host runtime supports team or teammate hooks

- Keep official team-task and teammate events inside the same Sejong authority model.
- Reject teammate output or task completion that claims Uigwe gate approval, final synthesis, final verification, consensus approval, or majority-vote authority.
- Add active context for bounded peer messages, shared task state, and lead-owned synthesis.

`SubagentStop`

- Reject worker outputs that claim Uigwe gate approval, final synthesis, or majority-vote authority.
- Require bounded evidence, risks, implementation notes, or verification observations back to the Sejong lead.

`Stop`

- Continue the turn when pending gates or missing verification would make completion premature.
- Continue the turn when `uigwe_promotion_required` remains pending, so decision-prep research cannot end as a final conclusion before Uigwe.
- Continue the turn when `seungjeongwon_receipt_required` remains pending, so
  goal-bearing implementation cannot end before a Seungjeongwon execution
  receipt exists.
- Continue the turn when any referenced ambiguity register still has `open`
  ambiguity items or pending question obligations.
- Continue the turn when any referenced Seungjeongwon run is active, broken, or invalid.
- Continue the turn when any referenced continuity capsule is broken or invalid.

`PreCompact`

- Check that the active context checkpoint has the required fields before compaction.
- Block compaction when an ambiguity-register reference is broken.
- Block compaction when a Seungjeongwon run reference is broken or invalid.
- Block compaction when a continuity capsule reference is broken or invalid.

`PostCompact`

- Re-inject the active context summary after compaction.
- Include active Seungjeongwon run ids and open todo counts when readable run
  artifacts are referenced by the active context.
- Include continuity capsule projections when readable capsules are referenced
  by the active context.

## Config

User-scope King Sejong install enables hooks through the local
`king-sejong-local` Codex plugin by default. The plugin hook is a thin adapter
that delegates to the canonical user-scope script under
`${CODEX_HOME:-~/.codex}/skills/sejong/docs/scripts/king_sejong_hooks.py`.
The installer owns a marked King Sejong plugin block and sets
`[features].hooks = true`. On macOS, installed hook path verification and
active-context `repo_root` matching normalize path case so `/Users/Junsu` and
`/Users/junsu` do not split the same workspace.

Older installs may still have a marked direct hook block in
`${CODEX_HOME:-~/.codex}/config.toml`. A normal user-scope reinstall removes
that direct block so plugin hooks are the single canonical hook source. The
explicit `--legacy-direct-hooks` installer option keeps direct hooks as a
fallback mode, but verification fails when direct hooks and plugin hooks are
enabled together.

Hooks are scoped by active context and repository-scoped run contexts. The reference hook script first reads `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/active-context.json`; if that pointer is missing or stale for the current workspace, it scans `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/*/*/king-sejong-context.json` and selects the newest valid context whose `repo_root` contains the current `cwd`. If an active context exists but no matching repo context is available, continuation events such as `UserPromptSubmit`, `SessionStart`, and `PostCompact` surface a compact `repo_mismatch=true` warning instead of silently applying the stale context. Other events remain quiet on mismatch unless a matching repo-scoped context is provided.

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
