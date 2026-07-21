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

Host-native Codex workers also require a `sejong.worker-resource-lease/v0.1-draft`
for their exact runtime group and a correlated
`sejong.worker-cleanup-receipt/v0.1-draft`. Terminal output alone does not close
their wave. Core rejects fan-in while a `codex-thread://` worker lacks cleanup
evidence, and only a `released` cleanup backed by `core_owned_exact` or
`host_owned_exact` capability can contribute to a passed fan-in. `preserved`,
`failed`, `orphaned`, and `audit_only` evidence blocks success and therefore
prevents another dependency wave from opening.

Backend selection performs this cleanup check before spawn. If the host does
not expose an exact runtime identity and supported release proof, the
host-native backend is unavailable for that run; the lead continues locally or
selects a Core-owned backend. Sejong does not create audit-only native workers
and hope to clean them up afterward.

For host-native Codex agents, `native_delegation_adapter.py` is a narrow receipt
projection boundary. It verifies that the worker was registered with backend
`native`, converts the host thread id to `codex-thread://<thread-id>`, and calls
the same Core terminal-receipt operation. It does not spawn, resume, message,
wait for, or close agents, and it does not create a second mailbox or fan-in
engine. The host owns agent lifecycle; DelegationRun owns budgets, waves,
receipts, the cleanup barrier, and fan-in. King Sejong never infers ownership
from process names or kills a host process from `SubagentStop`; the host must
provide an exact thread or runtime-group identity and cleanup proof.

Core computes fan-in. A wave passes only when every terminal receipt is
`completed` and every required host-native cleanup receipt is `released`.
Missing receipts block fan-in, `timed_out` or `failed` terminal receipts produce
a failed fan-in, and unresolved cleanup or `blocked` terminal receipts produce
a blocked fan-in. A failed or blocked fan-in cannot unlock a downstream wave.

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
python3 docs/sejong/scripts/worker_resource_lease.py create <lease.json> \
  --lease-id lease-planner --run-id example --wave-id discovery --worker-id planner \
  --backend native --backend-worker-ref codex-thread://thread-123 \
  --cleanup-capability host_owned_exact --resource-id runtime-planner \
  --resource-kind host_runtime_group --identity-ref codex-thread://thread-123 \
  --ownership-source host_reported --cleanup-policy automatic
python3 docs/sejong/scripts/worker_resource_lease.py transition <lease.json> --status releasing
# The host performs exact thread/runtime teardown and returns a proof reference.
python3 docs/sejong/scripts/worker_resource_lease.py transition <lease.json> \
  --status released --proof-ref host-cleanup://thread-123
python3 docs/sejong/scripts/native_delegation_adapter.py record-cleanup <run.json> \
  --receipt-id cleanup-planner --agent-thread-id thread-123 \
  --worker-resource-lease <lease.json>
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
When the host cannot supply exact ownership or teardown proof, record an
`audit_only` or failed cleanup disposition and stop opening native waves; do not
substitute a name-based process scan.

All mutations use a per-run lock and atomic state replacement. Runtime files
belong under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user
explicitly promotes an artifact.
