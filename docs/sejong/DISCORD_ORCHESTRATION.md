# Discord-first Codex Orchestration

**Status:** Local contract foundation, draft v0.1

This surface defines a conservative Discord-first path without making Discord,
Hermes, Agent Company, a Codex worker, or a reviewer a second King Sejong
authority.

```text
validated Discord adapter
-> Terra@Hermes controller
-> King Sejong Core route and Uigwe gates
-> Agent Company staffing projection
-> TeamExecutor worktree and write lease when mutation is allowed
-> one new fixed-model Codex process for the ticket
-> DelegationRun terminal receipt and Core fan-in
-> one new read-only Sol reviewer process
-> optional read-only Antigravity shadow opinion
-> Core final verification and evidence-based ticket state
-> Discord projection
```

The source checkout contains contracts and local helpers only. It does not
configure Discord, change Hermes Agent, provision Codex authentication, send a
message, or launch a live Codex process during tests.

## Authority boundary

| Surface | Owns | Cannot own |
| --- | --- | --- |
| Discord adapter | signature/transport validation, schema conversion, outbound projection | routing, approval, shell composition, completion |
| Terra@Hermes | controller transport and status coordination | code changes, gate overrides, final verification |
| King Sejong Core | routing, Uigwe gates, delegation budgets, leases, receipts, fan-in, final state | hidden external execution |
| Agent Company | role staffing projected from a sealed Core decision | a second route, model change, lease, approval, review verdict, completion |
| Luna | bounded implementation evidence from one fixed-model run | self-approval or completion |
| Sol | fresh candidate-bound read-only approval recommendation | mutation or final completion |
| Antigravity | read-only shadow second opinion and metrics | sole approval, canonical state mutation, automatic promotion |

`Terra` is a controller slot, not an implementation worker. The controller
applies the Core decision and must not make code changes. `Luna`, `Sol`, and
`Antigravity` are policy slots; each process still records the exact immutable
model identifier selected by Core.

## P0 control boundary

`discord-orchestration.schema.json` covers the additive v0.1 control and
runtime formats. The inbound parser accepts only the closed command variants
`create_ticket`, `approve`, `cancel`, and `status`. Authorization is supplied
separately through host-owned guild, channel, user, and required-role
allowlists. An inbound actor cannot authorize itself.

The parser rejects raw process and shell fields. A create-ticket objective is
passed on standard input; it is never interpolated into argv. The only Codex
launch form constructed by the runner is equivalent to:

```text
<absolute-codex-path> exec --model <opaque-model-token> --sandbox <mode>
  --cd <absolute-workspace> --ephemeral --json -
```

The process adapter uses argv with `shell=false`. Model and sandbox are fixed
for the lifetime of the process. Event and idempotency keys are sealed under
`${SEJONG_HOME}/state/discord/`; target host/repository mappings are exact and
host-owned.

## P1 runner, delegation, and evidence

Dry-run uses a process implementation that fails if invoked. Production code
depends on a process protocol, so tests use fakes or harmless local helper
processes and never invoke Codex. The concrete adapter:

- starts one child process per executable ticket;
- bounds combined stdout and stderr to 1 MiB in the persisted receipt;
- applies the ticket timeout;
- checks the Core cancellation marker before launch and while the child runs;
- terminates, then kills after a bounded grace period when needed;
- records failure, timeout, and cancellation explicitly.

Executable mutation tickets must bind to an existing TeamExecutor worker,
worktree, scope lease, and active DelegationRun wave. The ticket runner validates that binding
instead of allocating its own worker authority. It then records the process
result through the existing `worker_terminal` receipt path. Core fan-in remains
the only dependency-wave reducer.

A successful process receipt has `completion_eligible=false`. The immutable
candidate handoff additionally binds:

- ticket and producer run;
- workspace path, base commit, head commit, and dirty state before and after;
- SHA-256 of the exact observed diff bytes;
- producer model and sandbox;
- structured verification commands and exit codes;
- artifact references, sizes, hashes, and verification references;
- unknowns, verification requirements, and constraints for the next run.

The handoff and evidence manifest are create-once runtime artifacts under
`${SEJONG_HOME}/runs/discord/<ticket-id>/`. Exit code zero is process evidence,
not a completion decision.

## P2 review and multi-Mac recovery

Review dispatches bind the ticket, candidate SHA-256, producer identity, and a
different reviewer identity and run. Sol dispatches are read-only and fresh.
Antigravity dispatches are always read-only shadows with no canonical-write
authority. A shadow approval by itself leaves the candidate in
`review_pending`.

Dispatch and review-receipt SHA-256 seals detect changed contract bytes; they
do not authenticate a reviewer. A later live controller must bind the recorded
reviewer run and process reference to the host-created Sol process before Core
accepts the receipt.

Even a valid Sol approval produces `final_verification_pending`. Only the Core
state reducer can emit `verified`, after a matching candidate-bound Core
verification receipt covers every declared requirement and cites evidence.
That state is the safe input for a later Discord projection.

Host heartbeats record capability names, repository path mappings, connection
state, and only an observation of Codex auth readiness. They never record a
credential. Cross-host write leases are repository-exclusive. A disconnected
or unknown host cannot receive a write lease. An apparently expired lease is
not stolen: an explicit matching recovery operation with an evidence reference
must release it first.

A worktree provides edit isolation and merge provenance. It is not a sandbox,
security boundary, or proof that a process stayed within scope. Codex sandbox
mode, host permissions, path-scope checks, and final diff verification remain
separate controls.

## P3 routing and promotion

Core routes by `task_class`, `risk_class`, and `verification_class`. A supplied
role name does not select a model. The sealed decision records Terra as
controller-only, one fixed Luna implementer model, one fixed read-only Sol
reviewer model, and an optional read-only Antigravity shadow model. High-risk
routes require approval before execution.

Shadow promotion is task-class specific. The current contract requires at
least three comparable runs, three independent reviews, positive measured
quality change, zero regressions, and an explicit approval reference. Passing
those checks creates only a `promotion_candidate`; automatic promotion remains
false.

Agent Company's `policies/discord-staffing.json` consumes the sealed Core
decision and maps the named slots to Company roles. It cannot change the route,
model, sandbox, approval gate, scope, lease, verdict, or completion state.

## Local-only rollout

1. Validate checked schemas and fixtures.
2. Run the contract-only dry-run below. It uses `/usr/bin/false` as a sealed
   executable placeholder, and the dry-run adapter proves it was not invoked.
3. In a later controlled host setup, add a real Discord signature adapter and
   Terra@Hermes transport while keeping the same input schema.
4. Register one target Mac, observe Codex auth state without secrets, and
   exercise heartbeat/disconnect recovery without starting workers.
5. Enable one low-risk repository and let Core/TeamExecutor allocate an
   isolated worktree and active write lease.
6. Enable one live fixed-model Codex implementer process, then a different new
   read-only Sol reviewer process. Keep Antigravity disabled or shadow-only.
7. Project only the Core evidence state back through the Discord adapter.

Exact local dry-run entry point from the King Sejong source root:

```bash
DISCORD_DEMO_ROOT="$(mktemp -d)"
python3 docs/sejong/scripts/discord_ticket_cli.py dry-run \
  --event docs/sejong/examples/discord-orchestration/low-risk.event.json \
  --policy docs/sejong/examples/discord-orchestration/local.policy.json \
  --targets docs/sejong/examples/discord-orchestration/local.targets.json \
  --workspace /tmp/king-sejong-discord-demo/worktree \
  --sejong-home "$DISCORD_DEMO_ROOT/sejong" \
  --json
```

Expected output includes `"status": "dry_run"` and
`"process_invoked": false`. Runtime receipts are written only beneath the
temporary `SEJONG_HOME` supplied to the command.

## Exact operational milestone

The first live milestone is intentionally narrow:

```text
one low-risk validated Discord ticket
-> one selected connected Mac
-> one Core/TeamExecutor isolated worktree and write lease
-> one new fixed-model Luna Codex process
-> one immutable candidate handoff
-> one different new read-only Sol reviewer process
-> one Core final-verification state
-> evidence returned through the Discord adapter
```

The following still require later live-environment setup and are not claimed by
this foundation: Discord signature/API integration, outbound Discord messages,
Hermes/Terra transport wiring, remote multi-Mac transport and heartbeat daemon,
real Codex auth provisioning, live Codex invocation, durable service
supervision, and any Antigravity invocation.
