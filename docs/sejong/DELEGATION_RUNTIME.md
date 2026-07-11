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

Core computes fan-in. A wave passes only when every required receipt is
`completed`. Missing receipts block fan-in, `timed_out` or `failed` receipts
produce a failed fan-in, and `blocked` receipts produce a blocked fan-in. A
failed or blocked fan-in cannot unlock a downstream wave.

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
python3 docs/sejong/scripts/delegation_run.py record-terminal <run.json> \
  --receipt-id receipt-planner --wave-id discovery --worker-id planner \
  --backend-worker-ref host://planner --worker-contract-ref contract://planner \
  --worker-output-ref output://planner --status completed --summary "planning complete" \
  --evidence-ref evidence://planning
python3 docs/sejong/scripts/delegation_run.py fan-in <run.json> \
  --wave-id discovery --output discovery-fan-in.json
python3 docs/sejong/scripts/delegation_run.py check <run.json>
python3 docs/sejong/scripts/seungjeongwon_run.py add-fan-in \
  --path <seungjeongwon-run.json> --delegation-run <run.json> \
  --receipt discovery-fan-in.json
```

All mutations use a per-run lock and atomic state replacement. Runtime files
belong under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user
explicitly promotes an artifact.
