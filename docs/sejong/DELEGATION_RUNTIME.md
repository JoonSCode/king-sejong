# Delegation Runtime

**Status:** Draft

King Sejong uses `sejong.delegation-run/v0.1-draft` as the backend-neutral
contract for bounded native subagents and TeamExecutor workers. It is an
execution ledger, not a process manager and not a new court surface.

The caller supplies four hard limits: total workers, concurrent workers, spawn
depth, and rounds. Core enforces those limits when workers register, launch, or
enter a dependency wave. Agent or product layers may choose defaults, but they
must not reimplement the enforcement engine.

## Dependency Waves

A wave names its required workers and earlier-wave dependencies. Core opens a
wave only after every dependency has a `passed` fan-in receipt. Workers inside
one wave may execute concurrently; different waves remain dependency ordered.
Once a worker is assigned to a declared wave, direct `launch-workers` calls are
rejected. Only `open-wave` may atomically reserve that worker after dependency
fan-in and concurrency checks pass. This applies equally to native and
TeamExecutor-backed workers.

Every launched worker must return one terminal receipt with its actual backend
worker reference, bounded worker contract, output reference, status, and
evidence. Native subagents and TeamExecutor workers use the same receipt shape.
Worker receipts have `evidence_only` authority.

A worker may also have one strict `worker_cleanup` receipt after terminal
evidence exists. Cleanup receipts bind the same run, wave, worker, backend, and
backend worker reference; identify one unique resource lease; and record one of
`released`, `preserved`, `failed`, or `audit_only` with status-consistent
resource sets, proof refs, and blocker disposition. Their authority is always
`cleanup_evidence_only`. The validator observes cleanup evidence but never
executes cleanup or manages a process.

Cleanup is optional for backward compatibility. A run with no cleanup receipts
keeps the existing terminal and fan-in contract. When cleanup evidence is
present, fan-in includes `cleanup_receipt_ids` that exactly cover the supplied
receipts. `released` evidence permits the terminal-derived result to stand;
`preserved` or `audit_only` can only downgrade wave readiness to `blocked`, and
`failed` can only downgrade it to `failed`. Cleanup never changes a terminal
status, replaces a missing terminal receipt, makes a failed terminal pass, or
acts as completion, gate, synthesis, or final-verification authority.

For host-native Codex agents, `native_delegation_adapter.py` is a narrow receipt
projection boundary. It verifies that the worker was registered with backend
`native`, converts the host thread id to `codex-thread://<thread-id>`, and calls
the same Core terminal-receipt operation. It does not spawn, resume, message,
wait for, or close agents, and it does not create a second mailbox or fan-in
engine. The host owns agent lifecycle; DelegationRun owns budgets, waves,
receipts, and fan-in.

Core computes fan-in. A wave passes only when every required terminal receipt
is `completed` and every supplied cleanup receipt is `released`. Missing
terminal receipts block fan-in, `timed_out` or `failed` terminals produce a
failed fan-in, and `blocked` terminals produce a blocked fan-in. A failed or
blocked fan-in cannot unlock a downstream wave.

Fan-in receipts have `orchestration_evidence_only` authority. They can be
attached to a Seungjeongwon run, but cannot approve Uigwe, synthesize a decision,
or complete verification. Attachment requires both the receipt file and its
validated delegation run. Seungjeongwon accepts only an exact, embedded,
`passed` fan-in receipt and records the delegation run as provenance.

## CLI

```bash
python3 docs/sejong/scripts/delegation_run.py init <run.json> \
  --run-id example --max-total-workers 4 --max-concurrency 2 \
  --max-spawn-depth 1 --max-rounds 3
python3 docs/sejong/scripts/delegation_run.py register-worker <run.json> \
  --worker-id planner --backend native --spawn-depth 0
python3 docs/sejong/scripts/delegation_run.py add-wave <run.json> \
  --wave-id discovery --worker-id planner
python3 docs/sejong/scripts/delegation_run.py open-wave <run.json> --wave-id discovery
python3 docs/sejong/scripts/native_delegation_adapter.py record-terminal <run.json> \
  --receipt-id receipt-planner --wave-id discovery --worker-id planner \
  --agent-thread-id thread-123 --worker-contract-ref contract://planner \
  --worker-output-ref output://planner --status completed --summary "planning complete" \
  --evidence-ref evidence://planning
python3 docs/sejong/scripts/delegation_run.py fan-in <run.json> \
  --wave-id discovery --output discovery-fan-in.json
python3 docs/sejong/scripts/delegation_run.py check <run.json>
python3 docs/sejong/scripts/seungjeongwon_run.py add-fan-in \
  --path <seungjeongwon-run.json> --delegation-run <run.json> \
  --receipt discovery-fan-in.json
```

TeamExecutor uses its own adapter path to supply the same receipt fields. Direct
`delegation_run.py record-terminal` remains the backend-neutral compatibility
surface, not a reason for native callers to invent host references manually.

Discord ticket execution uses this same TeamExecutor and DelegationRun path.
The fixed-model process runner validates the existing worker, worktree, active
scope leases, and open wave, then projects its bounded process receipt through
`record_terminal_receipt`. It does not allocate a competing worker budget,
lease, mailbox, or fan-in engine. Candidate handoff and independent review are
later evidence gates; a completed worker receipt is never final verification.

All mutations use a per-run lock and atomic state replacement. Runtime files
belong under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user
explicitly promotes an artifact.
