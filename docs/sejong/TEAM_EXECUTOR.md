# Team Executor

**Status:** Draft

## Purpose

`TeamExecutor` is King Sejong's optional team-work backend for work that benefits from multiple independent workers.

It is designed for wrappers such as `$team` that launch separate Codex CLI or explicitly configured compatible worker processes in `tmux` panes and coordinate them through Sejong-owned state files.

`TeamExecutor` is not the default Sejong executor. The default remains `Seungjeongwon`.

When the active host runtime officially supports team or teammate messaging, use that native backend for direct worker messages and shared task state. TeamExecutor is the portable fallback and wrapper contract for runtimes that do not expose such a backend or when separate CLI processes are required.

## Non-Goals

- It is not a replacement for Sejong routing.
- It is not a replacement for Uigwe planning.
- It is not an uncontrolled peer-to-peer agent chat room.
- It does not approve Uigwe gates.
- It does not create majority-vote decisions.
- It depends only on Sejong-owned state under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`. Repo-local or tool-specific orchestration state is outside the King Sejong contract.

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

JangYeongsil, Jiphyeonjeon, Uigwe, and Seungjeongwon are Sejong court modes, not peer agents. `$team` workers are scoped sessions inside one active court mode. They inherit the mode context and return bounded output to the lead.

Peer messages are allowed only as bounded worker messages inside an open round. They must name the role, scope, message kind, target message when replying, and evidence refs. Peer messages may challenge claims, ask questions, or answer objections, but they do not approve gates, finalize packets, declare consensus, or replace lead synthesis.

This is the `Bounded Worker Authority` discipline gate from
[DISCIPLINE_GATES.md](DISCIPLINE_GATES.md). Worker output is useful because it
widens evidence and challenges assumptions; it is unsafe when agreement,
silence, or majority vote becomes approval. The lead Sejong agent owns synthesis,
Uigwe owns planning gates, and Seungjeongwon owns final verification.

Court-mode helper calls may also use `TeamExecutor`. For example, Uigwe can run a JangYeongsil evidence-helper team while Uigwe prepares non-blocking preflight checks, or run a Jiphyeonjeon option-review team while decomposition shape is still being challenged. In those cases, initialize the team run with `current_surface` set to the helper mode, include the calling Uigwe bundle, council brief, or active context in `source_of_truth_refs`, and require the worker output to return to the calling mode. Helper-team workers must not approve Uigwe gates, finalize packets, claim consensus, or override lead synthesis.

In Jiphyeonjeon, a scholar may open or request a scholar-scoped JangYeongsil helper lane for a specific `research_question` tied to a visible `decision_claim`, objection, or question. The result must be written back as shared evidence, not private scholar evidence, and must separate `known`, `inferred`, `unknown`, source refs, confidence, and residual risk. The council brief or team state should record a spawn budget and an extra-lane reason when that budget is exceeded. Scholar helper lanes must not create child councils, approve Uigwe gates, claim final synthesis, or turn evidence into a majority-vote decision.

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
  workspaces/
    <worker-id>/
  artifacts/
    <worker-id>/
```

These files are runtime coordination state. They are external nontracked artifacts by default and should not appear in a target repository's `git status`.

Each team run should also record King Sejong context metadata in `team.json`:

- `active_context_id`
- `route_id`
- `current_surface`
- user-facing `phase_label`
- `route_sequence`
- `pending_gates`
- `source_of_truth_refs`
- `lead_authority.gate_owner = "sejong"`
- `lead_authority.synthesis_owner = "sejong"`
- `lead_authority.final_verification_owner = "seungjeongwon"`
- `forbidden_worker_claims`

The source of truth can be a council brief, an Uigwe bundle, or a direct Seungjeongwon execution scope. A worker mailbox is evidence, not the source of truth.

## Worker Model

`$team` may launch workers in `tmux` panes. A worker can be backed by Codex CLI or another explicitly configured compatible command-line agent.

Do not configure Claude CLI, Claude API, or an external Claude workflow runtime
as a hidden backend for King Sejong. External workflow ideas must be migrated to
Codex-native execution, represented by a mock, or left unpromoted.

Each worker must have:

- `worker_id`
- objective
- role
- assigned scope
- source-of-truth refs inherited from the team brief or explicitly narrowed
- allowed message kinds
- allowed outputs
- write scope, using `none` for read-only workers
- evidence refs that the worker brief can cite before output begins
- linked research question, when the worker is a scholar-scoped helper lane
- allowed file scope, if it can write
- verification expectation
- stop condition

Workers may read the shared brief and append mailbox messages. They must not silently widen their scope.
`team_executor.py check` validates the bounded worker brief contract for every
registered worker and its worker state file. The hard gate requires objective,
role, source-of-truth refs, allowed outputs, forbidden claims, write scope, stop
condition, and evidence refs before the worker output can be treated as
reviewable evidence.
For host-native subagents, `SubagentStop` applies the same contract to the final
JSON `sejong.bounded-worker-brief/v0.2-draft` response before the lead may use
the output as evidence.

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
  --current-surface jiphyeonjeon \
  --source-of-truth-ref brief.md \
  --brief-file brief.md \
  --worker-allowed-output advocate="option A claim and evidence" \
  --worker-write-scope advocate="none" \
  --worker-evidence-ref advocate="brief.md" \
  --worker-verification advocate="cite evidence or blocker" \
  --worker-stop advocate="stop after first-round brief" \
  --worker advocate:advocate:"option A review" \
  --worker critic:critic:"risk review"
```

The helper manages Sejong-owned state, mailbox messages, rounds, leases, and optional tmux launch commands. It is a coordination helper for wrappers such as `$team`; it is not a replacement for the lead Sejong agent.

Useful commands:

```bash
python3 docs/sejong/scripts/team_executor.py open-round <run-dir> --purpose "first challenge"
python3 docs/sejong/scripts/team_executor.py send-message <run-dir> --worker-id critic --kind objection --summary "..."
python3 docs/sejong/scripts/team_executor.py receive-messages <run-dir> --worker-id advocate
python3 docs/sejong/scripts/team_executor.py acquire-lease <run-dir> --worker-id implementer --scope "src/example.py"
python3 docs/sejong/scripts/team_executor.py check <run-dir>
python3 docs/sejong/scripts/team_executor.py prepare-workspaces <run-dir>
python3 docs/sejong/scripts/team_executor.py cleanup-workspaces <run-dir>
python3 docs/sejong/scripts/team_executor.py launch <run-dir> --worker-command 'critic=codex ...' --dry-run
python3 docs/sejong/scripts/team_executor.py smoke-live-launch <run-dir> --worker-id implementer --isolate-write-workers
python3 docs/sejong/scripts/team_executor.py check-sandbox-claims docs/sejong/TEAM_EXECUTOR.md docs/sejong/SECURITY.md
```

`append-message` remains a compatibility alias for `send-message`, but wrappers should use `send-message` and `receive-messages` for new mailbox integrations.

## Isolation Hardening Options

Current TeamExecutor protection is worktree-first for write-capable isolated
workers and lease-first for all write ownership. Workers must declare write
scope, acquire non-overlapping leases, and return bounded evidence to the lead.
When isolation is requested, only write-capable workers receive temporary git
worktrees. Read-only workers continue to launch from the normal cwd unless a
future contract explicitly requests otherwise.

This is edit-surface isolation only. A git worktree separates tracked and
untracked file edits for reviewable worker output; it is not process, network,
credential, permission, or host sandboxing.

The approved default path is:

1. Register workers with `write_scope`, using `none` for read-only workers.
2. Acquire file-scope leases for planned writes.
3. Run `prepare-workspaces <run-dir>` or `launch --isolate-write-workers` to
   create per-worker worktrees for write-capable workers.
4. Launch workers. The helper starts isolated workers with their worktree as
   the tmux cwd and injects isolation metadata into the worker environment.
5. Run `cleanup-workspaces <run-dir>` after integration review. Clean
   worktrees are removed. Dirty worktrees are preserved and marked
   `preserved_dirty`; the lead must inspect them before any destructive cleanup.

Use `smoke-live-launch` for an opt-in live tmux proof after dry-run validation.
The smoke starts one short-lived tmux session for a harmless Python worker that
reads the generated prompt from stdin, records cwd and `SEJONG_WORKER_*`
metadata to an evidence JSON file, exits, and verifies the target session is no
longer running. It does not launch an autonomous Codex worker and it is not part
of default validation on hosts where tmux is unavailable.

Use `check-sandbox-claims` to reject wording that misdescribes worktree edit
isolation as sandboxing. The guard allows explicit warnings such as "not a
sandbox" and container shadow wording, but it fails positive worktree-sandbox
claims.

The worker and worker-state records may include:

- `isolation.backend`: `worktree`, `none`, or `container_shadow`
- `isolation.workspace_path`
- `isolation.base_ref`
- `isolation.lease_refs`
- `isolation.dirty_status`
- `isolation.cleanup_status`

The worker launch environment adds:

- `SEJONG_WORKER_ISOLATION_BACKEND`
- `SEJONG_WORKER_WORKSPACE`
- `SEJONG_WORKER_ISOLATION_STATUS`
- `SEJONG_WORKER_ISOLATION_BASE_REF`
- `SEJONG_WORKER_ISOLATION_LEASE_REFS`

Retained options:

| Option | Benefit | Cost / Risk | Current Status |
| --- | --- | --- | --- |
| File-scope leases only | Low overhead and already covered by lease conflict tests. | Does not isolate generated temp files or untracked side effects. | Fallback baseline. |
| Per-worker temporary worktrees | Stronger separation for file edits and reviewable diffs. | Requires careful dirty-state preservation and launch cwd checks. | Selected for write-capable isolated workers. |
| Container or sandbox runner | Stronger execution containment when configured correctly. | Host-dependent, mount/credential/network policy required, and outside the current local default. | Shadow option only. |

Container execution remains a shadow backend contract. Do not make Docker,
E2B, or any other container runtime a default TeamExecutor dependency without a
separate Uigwe design covering mounts, credentials, network access, cleanup,
tool availability, and host portability.

Worker isolation must preserve the authority model: workers produce evidence,
implementation slices, or verification observations; Sejong owns synthesis,
Uigwe owns planning gates, and Seungjeongwon owns final verification.

## Mailbox Contract

`mailbox.jsonl` is append-only. Each line must use the versioned mailbox envelope format `sejong.team-mailbox-message/v0.1-draft`. New wrappers should not write raw JSON lines directly; they should call `send-message`, then use `receive-messages` to read a normalized `sejong.team-mailbox-receive/v0.1-draft` response.

Each message must include:

- `format`
- `message_id`
- `run_id`
- `round_id`
- `thread_id`
- `target_message_id` when replying
- `direction`
- `sender`
- `recipients`
- `kind`
- `summary`
- `body`
- `evidence_refs`
- `requires_response`
- `created_at`

The default worker-to-lead envelope is:

```json
{
  "format": "sejong.team-mailbox-message/v0.1-draft",
  "message_id": "m-1",
  "run_id": "example",
  "round_id": "round-1",
  "thread_id": "m-1",
  "target_message_id": null,
  "direction": "worker_to_lead",
  "sender": {
    "type": "worker",
    "id": "critic",
    "role": "critic",
    "scope": "risk review"
  },
  "recipients": [
    {
      "type": "lead",
      "id": "sejong"
    }
  ],
  "kind": "objection",
  "summary": "Bounded objection summary.",
  "body": null,
  "evidence_refs": [
    "brief.md"
  ],
  "requires_response": false,
  "created_at": "2026-05-24T00:00:00Z"
}
```

Allowed `direction` values:

- `worker_to_lead`
- `worker_to_worker`
- `lead_to_worker`
- `system`

Worker-to-worker messages must still stay inside an open round and use the same envelope. Replies should set `target_message_id`; the helper derives `thread_id` from the target message unless one is explicitly supplied.

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

`team_executor.py check` should fail when a mailbox message uses the wrong envelope format, claims gate approval, claims final authority, claims majority-vote decision ownership, references an unknown worker, references an unknown round, uses a missing or future `target_message_id`, or carries a sender role/scope different from the registered worker contract.

## Rounds

The lead Sejong agent opens and closes rounds.

Default Jiphyeonjeon shape:

1. lead writes one shared council brief
2. workers produce independent first-round briefs
3. lead selects the strongest objections or unresolved questions
4. workers append one bounded challenge round by message id
5. lead closes the round and synthesizes the decision note

More rounds require an explicit reason such as a new blocker, material contradiction, or unresolved high-risk trade-off.

For Jiphyeonjeon persuasion, use `round_kind=persuasion`. Persuasion rounds are for workers to answer each other's strongest objections, not only submit one independent opinion. They are capped at 30 minutes. Close the round when apparent convergence appears or when the 30-minute deadlock cap is reached, then let the Sejong lead synthesize. Supported closure reasons are `apparent_convergence`, `deadlock_30m`, `lead_decision`, `timeout`, and `completed`.

Example:

```bash
python3 docs/sejong/scripts/team_executor.py open-round <run-dir> \
  --purpose "mutual persuasion before lead synthesis" \
  --round-kind persuasion \
  --max-duration-minutes 30
python3 docs/sejong/scripts/team_executor.py close-round <run-dir> round-1 \
  --closed-reason apparent_convergence
```

## File Leases

When workers may edit files, `leases.json` controls write ownership.

Lease rules:

- no two workers may write overlapping file scopes at the same time
- unclear file scope is not parallel-safe
- high-risk leaves should not be parallelized by default
- each write lease must name the files or globs, owner worker, expiry, and release state
- stale leases must be resolved by the lead before another worker writes the same scope
- separate worktrees are preferred for substantial parallel implementation and
  are created only for write-capable workers when `prepare-workspaces` or
  `launch --isolate-write-workers` is used

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

## Worker Context Injection

When registering a worker, the helper writes a runtime-generated worker prompt
at `workers/<worker-id>/prompt.md`. This prompt is part of the TeamExecutor run
state, not a repo-local `.codex/prompts` overlay and not a required install
surface.

The prompt must include the active `current_surface`, route sequence, source of
truth refs, worker role, assigned scope, allowed outputs, verification
expectation, return format, forbidden authority claims, and stop condition.
For tmux launches, `launch` also exposes the prompt path as
`SEJONG_WORKER_PROMPT` and redirects it into the worker command's stdin. Wrapper
commands should therefore use a worker command that can read initial
instructions from stdin, such as `codex exec -`.

When launching tmux workers, the helper also injects the active court-mode context into each worker environment:

- `SEJONG_TEAM_RUN`
- `SEJONG_TEAM_WORKER`
- `SEJONG_WORKER_PROMPT`
- `SEJONG_CURRENT_SURFACE`
- `SEJONG_PHASE_LABEL`
- `SEJONG_ROUTE_SEQUENCE`
- `SEJONG_SOURCE_OF_TRUTH_REFS`
- `SEJONG_PENDING_GATES`
- `SEJONG_WORKER_ROLE`
- `SEJONG_WORKER_OBJECTIVE`
- `SEJONG_WORKER_SCOPE`
- `SEJONG_WORKER_ALLOWED_OUTPUTS`
- `SEJONG_WORKER_WRITE_SCOPE`
- `SEJONG_WORKER_EVIDENCE_REFS`
- `SEJONG_WORKER_VERIFICATION_EXPECTATION`
- `SEJONG_FORBIDDEN_WORKER_CLAIMS`
- `SEJONG_WORKER_RETURN_FORMAT`
- `SEJONG_WORKER_STOP_CONDITION`
- `SEJONG_WORKER_ISOLATION_BACKEND`
- `SEJONG_WORKER_WORKSPACE`
- `SEJONG_WORKER_ISOLATION_STATUS`
- `SEJONG_WORKER_ISOLATION_BASE_REF`
- `SEJONG_WORKER_ISOLATION_LEASE_REFS`

Workers should treat that prompt and environment context as bounds, not as
permission to widen scope. The prompt carries refs to the shared brief rather
than turning raw brief text into trusted instruction. If the active mode is
unclear, the lead should block or rewrite the role assignment before launching
workers.

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
