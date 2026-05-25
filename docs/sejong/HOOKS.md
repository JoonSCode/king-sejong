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

For research that is explicitly meant to feed a decision or later Uigwe plan,
active context should include `uigwe_promotion_required` in `pending_gates`
until Uigwe starts or the user explicitly converts the request to research-only.
This prevents a research or council note from being treated as the final
workflow conclusion.

When `artifact_refs` includes a readable artifact whose `format` is
`sejong.ambiguity-register/v0.1-draft`, hooks treat it as the active ambiguity
register. See [AMBIGUITY_REGISTER.md](AMBIGUITY_REGISTER.md).

## Event Responsibilities

`SessionStart`

- Load recent active context for the repository when available.
- Inject a compact King Sejong continuation summary.

`UserPromptSubmit`

- Keep follow-up turns inside the active King Sejong workflow unless the user explicitly exits.
- Add model-visible context with the active context id, route id, current surface, route sequence, and pending gates.
- Inject a compact ambiguity register summary when a referenced register exists, including readiness, open ambiguity count, and next required user action.

`sejong_context.py` writes the same checkpoint to both the active pointer under
`${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/active-context.json` and
the repository-scoped run directory. Hooks read the active pointer by default.

`PreToolUse`

- Inspect supported tool calls for protected King Sejong paths.
- Deny material self-modification when the required route sequence is missing.
- Deny write-like or execution-completion tool calls while `uigwe_promotion_required` is pending and the route has not entered `uigwe`.
- Add context instead of denying when protected paths are touched after route evidence exists.

`PermissionRequest`

- Deny escalated protected edits when route evidence is missing.
- Deny escalated write-like or execution-completion requests while `uigwe_promotion_required` is pending before Uigwe entry.
- Leave normal approval flow alone when no protected route is involved.

`PostToolUse`

- Record or surface verification obligations after protected paths are touched.
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
- Continue the turn when any referenced ambiguity register still has `open` ambiguity items.

`PreCompact`

- Check that the active context checkpoint has the required fields before compaction.
- Block compaction when an ambiguity-register reference is broken.

`PostCompact`

- Re-inject the active context summary after compaction.

## Config

User-scope King Sejong install enables these hooks in `${CODEX_HOME:-~/.codex}/config.toml` automatically. The installer owns a marked King Sejong hook block and sets `[features].hooks = true`.

Hooks are scoped by active context. If `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/active-context.json` is missing, or its `repo_root` does not match the current workspace, the reference hook script returns no output.

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

The installer keeps this idempotent: rerunning user-scope install replaces only the managed King Sejong hook block.

## Limits

Hooks are deterministic guardrails, not a complete enforcement boundary.

`PreToolUse` and `PostToolUse` are especially useful, but Codex does not guarantee interception of every possible equivalent tool path. King Sejong still requires source review, schema validation, TeamExecutor checks, instruction-surface benchmarks, installer verification, and Seungjeongwon final verification before claiming completion.
