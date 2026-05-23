# Team Executor

**Status:** Draft

## Purpose

`TeamExecutor` is King Sejong's optional team-work backend for work that benefits from multiple independent workers.

It is designed for wrappers such as `$team` that launch separate Codex CLI, Claude CLI, or other compatible worker processes in `tmux` panes and coordinate them through Sejong-owned state files.

`TeamExecutor` is not the default Sejong executor. The default remains `Seungjeongwon`.

## Non-Goals

- It is not a replacement for Sejong routing.
- It is not a replacement for Uigwe planning.
- It is not a peer-to-peer agent chat room.
- It does not approve Uigwe gates.
- It does not create majority-vote decisions.
- It does not depend on `.omx` paths or OMX state. OMX-specific state must not be part of the King Sejong contract.

## Relationship To Sejong

Sejong owns routing, synthesis, gates, and final verification.

`TeamExecutor` may supply bounded worker output, but it never becomes the decision maker. The safe shape is:

```text
Sejong lead
-> selected surface and source-of-truth brief
-> $team worker wrapper
-> mailbox and state files
-> lead synthesis and verification
```

For Uigwe-backed execution, the Uigwe bundle remains the source of truth. For Jiphyeonjeon, the shared council brief remains the source of truth.

## State Root

`TeamExecutor` state belongs under the Sejong artifact root:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/
```

A run directory should use this shape:

```text
state/team/<run-id>/
  brief.md
  team.json
  rounds.json
  mailbox.jsonl
  leases.json
  workers/
    <worker-id>/state.json
    <worker-id>/notes.md
  artifacts/
    <worker-id>/
```

These files are runtime coordination state. They are external nontracked artifacts by default and should not appear in a target repository's `git status`.

Each team run should also record King Sejong context metadata in `team.json`:

- `active_context_id`
- `route_id`
- `source_of_truth_refs`
- `lead_authority.gate_owner = "sejong"`
- `lead_authority.synthesis_owner = "sejong"`
- `lead_authority.final_verification_owner = "seungjeongwon"`
- `forbidden_worker_claims`

The source of truth can be a council brief, an Uigwe bundle, or a direct Seungjeongwon execution scope. A worker mailbox is evidence, not the source of truth.

## Worker Model

`$team` may launch workers in `tmux` panes. A worker can be backed by Codex CLI, Claude CLI, or another compatible command-line agent.

Each worker must have:

- `worker_id`
- role
- assigned scope
- allowed message kinds
- allowed file scope, if it can write
- verification expectation
- stop condition

Workers may read the shared brief and append mailbox messages. They must not silently widen their scope.

Workers must not claim:

- Uigwe gate approval
- final synthesis
- final verification
- majority-vote decisions
- consensus as approval

## Reference Helper

The installed docs include a small reference helper:

```bash
python3 docs/sejong/scripts/team_executor.py init \
  --run-id example \
  --active-context-id ctx-example \
  --route-id route-example \
  --source-of-truth-ref brief.md \
  --brief-file brief.md \
  --worker advocate:advocate:"option A review" \
  --worker critic:critic:"risk review"
```

The helper manages Sejong-owned state, mailbox messages, rounds, leases, and optional tmux launch commands. It is a coordination helper for wrappers such as `$team`; it is not a replacement for the lead Sejong agent.

Useful commands:

```bash
python3 docs/sejong/scripts/team_executor.py open-round <run-dir> --purpose "first challenge"
python3 docs/sejong/scripts/team_executor.py append-message <run-dir> --worker-id critic --role critic --scope "risk review" --kind objection --summary "..."
python3 docs/sejong/scripts/team_executor.py acquire-lease <run-dir> --worker-id implementer --scope "src/example.py"
python3 docs/sejong/scripts/team_executor.py check <run-dir>
python3 docs/sejong/scripts/team_executor.py launch <run-dir> --worker-command 'critic=claude ...' --dry-run
```

## Mailbox Contract

`mailbox.jsonl` is append-only. Each message should include:

- `message_id`
- `run_id`
- `round_id`
- `worker_id`
- `role`
- `scope`
- `kind`
- `target_message_id` when replying
- `summary`
- `evidence_refs`
- `created_at`

Allowed `kind` values:

- `claim`
- `objection`
- `question`
- `response`
- `evidence_ref`
- `risk`
- `status`
- `blocker`
- `verification`

The mailbox is coordination evidence, not a second source of truth. Worker agreement, mailbox consensus, or silence is never approval, verification, or a gate decision.

`team_executor.py check` should fail when a mailbox message claims gate approval, final authority, or majority-vote decision ownership.

## Rounds

The lead Sejong agent opens and closes rounds.

Default Jiphyeonjeon shape:

1. lead writes one shared council brief
2. workers produce independent first-round briefs
3. lead selects the strongest objections or unresolved questions
4. workers append one bounded challenge round by message id
5. lead closes the round and synthesizes the decision note

More rounds require an explicit reason such as a new blocker, material contradiction, or unresolved high-risk trade-off.

## File Leases

When workers may edit files, `leases.json` controls write ownership.

Lease rules:

- no two workers may write overlapping file scopes at the same time
- unclear file scope is not parallel-safe
- high-risk leaves should not be parallelized by default
- each write lease must name the files or globs, owner worker, expiry, and release state
- stale leases must be resolved by the lead before another worker writes the same scope
- separate worktrees are preferred for substantial parallel implementation

Without a valid lease, a worker may only produce analysis, review, or verification evidence.

## Surface-Specific Use

### Jiphyeonjeon

Best fit.

Use `$team` when a decision benefits from cross-examination across advocate, critic, specialist, operator, or risk-review roles. Workers may answer each other's bounded claims and objections through the mailbox, but the lead Sejong agent owns the final recommendation, rejected options, risks, confidence, and next surface.

### JangYeongsil

Allowed for independent research branches.

Each worker should own a distinct source, subsystem, history window, or experiment. The lead reconciles conflicts and marks known, inferred, and unknown material.

### Uigwe

Preflight only before gates.

Workers may inventory artifacts, check readiness, scan missing context, or review risk. They must not approve gates, finalize canonical packets, or create competing `spec.md`, `rationale.md`, or `goal-tree.json` files.

### Seungjeongwon

Allowed for execution only when dependencies and file scopes are independent.

Workers may implement, critique, or verify disjoint leaves. The lead or Seungjeongwon executor owns integration, final verification, and feedback.

## Pipes

Pipes may be used for ephemeral progress events from tmux workers.

Durable decisions, blockers, evidence, verification, and round closure belong in `mailbox.jsonl`, `rounds.json`, worker notes, or execution feedback. Do not treat pipe output as durable evidence.

## Failure Handling

Block or downgrade to direct Seungjeongwon execution when:

- the source-of-truth brief is unclear
- the team run lacks active King Sejong context metadata
- worker scopes overlap
- a worker edits without a lease
- a worker claims Uigwe gate approval, final synthesis, final verification, or majority-vote decision authority
- mailbox messages contradict the Uigwe bundle or council brief
- a tmux worker stalls and the lead cannot prove its state
- verification cannot be reproduced from durable evidence

When blocked, report the blocker and recommend one re-entry target when possible.
