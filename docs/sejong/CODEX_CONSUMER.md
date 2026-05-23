# Uigwe Codex Consumer Draft

**Status:** Draft
**Applies To:** the default reference consumer for `Uigwe`

## Purpose

The Codex consumer is the default execution-facing implementation for Uigwe `Plan Packet` handoff.

Its job is to consume executable leaves safely inside Codex without collapsing Uigwe into an execution-only system.

The Codex consumer is not a planner.

It must:

- consume executable leaves only
- respect the selected plan and retained dependency structure
- apply selective review where risk justifies it
- report execution state back into the Uigwe lifecycle

It must not:

- redefine scope on its own
- redesign the chosen approach on its own
- silently skip unresolved blockers
- invent missing planning details that should trigger re-entry

## Inputs

The Codex consumer expects the following inputs:

- a valid `Plan Packet`
- a valid `goal-tree.json`
- the supporting human-facing planning artifacts:
  - `spec.md`
  - `rationale.md`

The consumer should treat these as authoritative in this order:

1. `Plan Packet`
2. `goal-tree.json`
3. `spec.md`
4. `rationale.md`

If these artifacts disagree materially, the consumer should block and escalate rather than improvise.

## Consumption Boundary

The Codex consumer may act only on nodes whose status is `executable_leaf`.

If a node is still:

- `candidate`
- `selected`
- `retained_alt`

then planning is incomplete for that node and the consumer must not execute it.

## Execution Lanes

The Codex consumer may choose among a small number of execution lanes based on leaf clarity, risk, and scope.

### 1. Direct Session

Use when:

- the leaf is low risk
- the file scope is narrow
- verification is straightforward
- no independent parallelism benefit exists

### 2. Single Subagent

Use when:

- the leaf is well specified
- the work is meaningfully isolated
- the leaf can benefit from focused implementation context

### 3. Reviewed Subagent

Use when:

- the leaf is medium or high risk
- the file scope crosses important boundaries
- the leaf has explicit `needs_critic` or `needs_verifier` hints

This lane may include:

- implementer subagent
- optional critic pass
- verifier pass

The consumer should use the lightest lane that preserves execution safety.

These lane names describe the default Codex subagent consumer. `$team` is an executor-level `TeamExecutor` backend, not a fourth default consumer lane. When `$team` is selected, use [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) for tmux worker state, mailbox, and lease rules, then emit ordinary execution feedback for completed, blocked, or invalidated leaves.

## Dispatch Rules

### Dependency Order

- dispatch only leaves whose dependencies are already `completed`
- never dispatch a leaf whose prerequisite is `blocked` or `invalidated`

### Parallel Safety

Leaves may run in parallel only when:

- they are dependency-independent
- their `file_scope` does not overlap
- neither leaf is marked high risk
- no explicit consumer hint forbids parallel execution

If file scope is unclear, assume the leaf is not parallel-safe.

### Context Packaging

When dispatching to a subagent, provide:

- the leaf contract fields
- the selected plan summary
- the relevant acceptance criteria
- the file scope
- the verification expectations
- only the minimum supporting context needed from `spec.md` and `rationale.md`

The consumer should avoid forwarding the full planning history unless it is actually needed.

### Team Coordination

For `$team` or other team-style execution, the consumer may use a mailbox only as coordination evidence, not as a second source of truth.

Mailbox messages should be append-only and typed:

- `claim`
- `objection`
- `question`
- `response`
- `evidence_ref`
- `risk`
- `status`
- `blocker`
- `verification`

Each message should include the role, scope, authoring worker id, and target message id when it replies to another message. The lead agent owns round boundaries, conflict resolution, final synthesis, and all approval gates.

Pipes may be used for ephemeral progress notifications from tmux workers, but durable decisions, blockers, and verification evidence should be written or summarized through the mailbox or final feedback contract. Do not treat pipe output, worker agreement, subagent agreement, or mailbox consensus as completion proof.

## Critic Policy

`critic` is selective.

Use a critic pass when:

- `risk_level` is `high`
- the leaf crosses design or ownership boundaries
- the leaf's verification is weak relative to its impact
- the leaf explicitly requests critic review through consumer hints

The critic should check:

- consistency with the selected plan
- architectural boundary violations
- missed simpler alternatives
- scope creep

The critic should not reopen planning unless the issue cannot be resolved within the leaf boundary.

## Verifier Policy

`verifier` is broadly applied.

At minimum, the verifier should confirm:

- the leaf's `done_criteria`
- the planned verification checks
- obvious mismatch between claimed completion and actual evidence

Verification evidence may include:

- test results
- diagnostics
- artifact existence
- focused diff review
- file-level inspection aligned to the leaf contract

If verification cannot be completed with the available evidence, the consumer should mark the leaf `blocked` rather than claim success.

## Feedback Contract

The Codex consumer must emit machine-readable feedback after execution attempts.

This feedback exists to:

- update leaf lifecycle state
- capture execution evidence
- surface blockers
- recommend planner re-entry when needed

The draft schema lives in:

- `codex-consumer-feedback.schema.json`

At minimum, feedback should carry:

- the `attempt_id` and `attempt_number` assigned by the executor handoff
- the `executor_result_path` that this feedback belongs to
- the same bundle fingerprint used by the executor result when available
- commit group ids for leaf updates when the executor uses commit-producing git policy

Default persistence rule for the current Uigwe draft:

- the executor chooses the canonical feedback path
- the consumer writes or returns feedback for that path
- for the current flat bundle model, this is normally the root-level `codex-consumer-feedback.json`

When Git commits are enabled, the consumer feedback should not force one commit per leaf.
Instead, each affected leaf may reference one or more `commit_group_ids`, and the executor result owns the detailed commit shas and worktree evidence.

## Escalation Rules

The consumer should escalate rather than guess when:

- a leaf contract is incomplete
- file scope is too vague to execute safely
- verification requirements contradict available tooling
- execution reveals upstream design instability
- repeated blocking suggests the problem is not local

These escalation target ids are machine-readable Uigwe re-entry values, not protocol stage ids or separate required skills.
`brainstorming` maps directly to `Design Exploration`.
`deep_interview` maps back to `Intent Clarification` (`deep-interview`).

Recommended escalation targets:

- `local_reexploration`
- `brainstorming`
- `deep_interview`
- `human_review`

### Escalate to Local Re-exploration

Use when:

- the leaf is executable in principle but needs local restructuring
- dependency order or scope can be repaired without changing the design

### Escalate to Design Exploration (`brainstorming`)

Use when:

- the selected design choice is no longer working in execution
- a retained alternative now looks clearly superior
- integration complexity exceeds the chosen approach

### Escalate to Intent Clarification (`deep_interview`)

Use when:

- the goal boundary is unstable
- the user intent appears misread
- execution repeatedly exposes unresolved non-goals or decision boundaries

### Escalate to Human Review

Use when:

- the action would be destructive or materially branching
- planning artifacts disagree
- the issue has external business consequences beyond the protocol's authority

## Status Updates

The consumer is expected to move leaves through these states:

- `executable_leaf -> dispatched`
- `dispatched -> completed`
- `dispatched -> blocked`
- `dispatched -> invalidated`

It may also recommend:

- `blocked -> selected`
- `blocked -> invalidated`

but those transitions should normally be applied by the planner after review, not by the consumer alone.

## Example Outcome Patterns

### Successful Execution

- leaf dispatched
- work implemented
- verification evidence collected
- feedback emitted with `completed`

### Local Block

- leaf dispatched
- execution reveals a missing file-scope detail
- feedback emitted with `blocked`
- escalation recommends `local_reexploration`

### Upstream Instability

- leaf dispatched
- execution reveals the chosen design path is misaligned
- feedback emitted with `blocked` or `invalidated`
- escalation recommends `brainstorming` or `deep_interview`

## Artifact Storage

Consumer feedback artifacts follow [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md) unless a caller explicitly requests repository-tracked promotion.

## Non-Goals

This draft does not yet define:

- the exact Codex prompt template for every execution lane
- automatic reviewer role selection heuristics beyond the current policy guidance
- multi-consumer arbitration when several consumers operate on one plan
